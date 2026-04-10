"""Optional Ollama-backed assistant helpers and JSON-driven loop execution."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .constants import DEFAULT_ASSISTANT_LOOPS_PATH


class OllamaAssistantService:
    def __init__(self, command: str="ollama"):
        self.command = command

    def list_models(self) -> List[Dict[str, Any]]:
        result = self._run_command(["list"], timeout=10)
        if not result["ok"]:
            return []
        lines = [line.rstrip() for line in result["output"].splitlines() if line.strip()]
        if len(lines) <= 1:
            return []
        models: List[Dict[str, Any]] = []
        for line in lines[1:]:
            parts = re.split(r"\s{2,}", line.strip())
            if not parts:
                continue
            name = parts[0].strip()
            size_text = parts[2].strip() if len(parts) > 2 else ""
            modified = parts[3].strip() if len(parts) > 3 else ""
            models.append(
                {
                    "name": name,
                    "size_text": size_text,
                    "size_b": self._parse_size_b(name, size_text),
                    "modified": modified,
                }
            )
        return models

    def choose_default_model(self, size_cap_b: float) -> Optional[str]:
        compatible = [
            model
            for model in self.list_models()
            if model["size_b"] is None or model["size_b"] <= size_cap_b
        ]
        if not compatible:
            return None
        compatible.sort(
            key=lambda item: (item["size_b"] is not None, item["size_b"] or 0.0, item["name"]),
            reverse=True,
        )
        return compatible[0]["name"]

    def summarize_service(self, model_name: str, service_payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Summarize this microservice in 6 bullet points. Focus on purpose, dependencies, and risks.\n\n"
            + json.dumps(service_payload, indent=2)
        )
        return self._run_model(model_name, prompt)

    def suggest_ui_schema(self, model_name: str, schema: Dict[str, Any], goal: str) -> Dict[str, Any]:
        prompt = (
            "Return JSON only. Suggest a revised ui_schema.json for this goal. Goal: "
            + goal
            + "\n\nCurrent schema:\n"
            + json.dumps(schema, indent=2)
        )
        return self._run_model(model_name, prompt)

    def chat(
        self,
        model_name: str,
        messages: Sequence[Dict[str, str]],
        system_prompt: str="",
        context: Optional[Dict[str, Any]]=None,
        max_history_messages: int=8,
    ) -> Dict[str, Any]:
        prompt = self._build_chat_prompt(
            messages=messages,
            system_prompt=system_prompt,
            context=context or {},
            max_history_messages=max_history_messages,
        )
        result = self._run_model(model_name, prompt)
        result["prompt"] = prompt
        return result

    def describe_model(self, model_name: str) -> Dict[str, Any]:
        target = str(model_name).strip()
        installed = next((item for item in self.list_models() if item["name"] == target), None)
        runtime_rows = self._parse_table_output(self._run_command(["ps"], timeout=10)["output"])
        runtime = next((item for item in runtime_rows if item.get("name") == target), None)
        show_result = self._run_command(["show", target], timeout=15) if target else {"ok": False, "output": "", "error": ""}
        show_summary = self._parse_show_output(show_result["output"]) if show_result["ok"] else {}
        host_stats = self._host_stats()
        status = "missing"
        if installed:
            status = "installed"
        if runtime:
            status = "loaded"
        return {
            "model_name": target,
            "status": status,
            "installed": installed is not None,
            "runtime_loaded": runtime is not None,
            "size_text": (installed or {}).get("size_text", "-"),
            "size_b": (installed or {}).get("size_b"),
            "modified": (installed or {}).get("modified", "-"),
            "architecture": show_summary.get("architecture", "-"),
            "parameters": show_summary.get("parameters", "-"),
            "context_length": show_summary.get("context_length", "-"),
            "embedding_length": show_summary.get("embedding_length", "-"),
            "quantization": show_summary.get("quantization", "-"),
            "processor": (runtime or {}).get("processor", "-"),
            "runtime_size": (runtime or {}).get("size", "-"),
            "until": (runtime or {}).get("until", "-"),
            "gpu": self._infer_gpu_label(runtime),
            "vram": (runtime or {}).get("size", "-") if runtime and "gpu" in str(runtime.get("processor", "")).lower() else "-",
            "cpu": host_stats["cpu"],
            "ram": host_stats["ram"],
            "ram_free": host_stats["ram_free"],
            "platform": host_stats["platform"],
            "capabilities": show_summary.get("capabilities", []),
            "show_ok": show_result.get("ok", False),
            "show_error": show_result.get("error", ""),
        }

    def _build_chat_prompt(
        self,
        messages: Sequence[Dict[str, str]],
        system_prompt: str,
        context: Dict[str, Any],
        max_history_messages: int,
    ) -> str:
        history = [item for item in messages if str(item.get("content", "")).strip()]
        recent = history[-max(1, int(max_history_messages or 1)) :]
        sections: List[str] = []
        if system_prompt.strip():
            sections.append("System Instructions\n-------------------\n" + system_prompt.strip())
        if context:
            sections.append("Grounding Context (JSON)\n------------------------\n" + json.dumps(context, indent=2))
        transcript_lines: List[str] = []
        for message in recent:
            role = str(message.get("role", "user")).strip().upper() or "USER"
            transcript_lines.append(role)
            transcript_lines.append(message.get("content", "").rstrip())
            transcript_lines.append("")
        transcript_lines.append("ASSISTANT")
        sections.append("Conversation\n------------\n" + "\n".join(transcript_lines).rstrip())
        return "\n\n".join(section for section in sections if section.strip())

    def _run_model(self, model_name: str, prompt: str) -> Dict[str, Any]:
        if not str(model_name).strip():
            return {"ok": False, "error": "No Ollama model selected.", "output": ""}
        result = self._run_command(["run", model_name], timeout=90, stdin_text=prompt)
        return {"ok": result["ok"], "error": result["error"], "output": result["output"]}

    def _run_command(self, args: Sequence[str], timeout: int=10, stdin_text: str | None = None) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                [self.command, *args],
                input=stdin_text,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
                check=False,
            )
        except Exception as exc:
            return {"ok": False, "error": str(exc), "output": "", "returncode": -1}
        return {
            "ok": result.returncode == 0,
            "error": result.stderr.strip(),
            "output": result.stdout.strip(),
            "returncode": result.returncode,
        }

    def _parse_table_output(self, output: str) -> List[Dict[str, str]]:
        lines = [line.rstrip() for line in output.splitlines() if line.strip()]
        if len(lines) <= 1:
            return []
        rows: List[Dict[str, str]] = []
        for line in lines[1:]:
            parts = re.split(r"\s{2,}", line.strip())
            if not parts:
                continue
            rows.append(
                {
                    "name": parts[0].strip() if len(parts) > 0 else "",
                    "id": parts[1].strip() if len(parts) > 1 else "",
                    "size": parts[2].strip() if len(parts) > 2 else "",
                    "processor": parts[3].strip() if len(parts) > 3 else "",
                    "context": parts[4].strip() if len(parts) > 4 else "",
                    "until": parts[5].strip() if len(parts) > 5 else "",
                }
            )
        return rows

    def _parse_show_output(self, output: str) -> Dict[str, Any]:
        summary: Dict[str, Any] = {"capabilities": []}
        current_section = ""
        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if not line.startswith(" "):
                current_section = stripped.lower()
                continue
            if current_section == "capabilities":
                summary["capabilities"].append(stripped)
                continue
            parts = re.split(r"\s{2,}", stripped, maxsplit=1)
            if len(parts) == 2:
                key = parts[0].replace(" ", "_")
                summary[key] = parts[1].strip()
        return summary

    def _infer_gpu_label(self, runtime: Optional[Dict[str, str]]) -> str:
        if not runtime:
            return "-"
        processor = str(runtime.get("processor", "")).strip()
        if not processor:
            return "-"
        return "enabled" if "gpu" in processor.lower() else "inactive"

    def _host_stats(self) -> Dict[str, str]:
        total_bytes = 0
        free_bytes = 0
        if os.name == "nt":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            memory_status = MEMORYSTATUSEX()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
                total_bytes = int(memory_status.ullTotalPhys)
                free_bytes = int(memory_status.ullAvailPhys)
        elif hasattr(os, "sysconf"):
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
            total_pages = int(os.sysconf("SC_PHYS_PAGES"))
            available_pages = int(os.sysconf("SC_AVPHYS_PAGES"))
            total_bytes = page_size * total_pages
            free_bytes = page_size * available_pages
        return {
            "cpu": str(os.cpu_count() or "-"),
            "ram": self._format_gb(total_bytes),
            "ram_free": self._format_gb(free_bytes),
            "platform": f"{platform.system()} {platform.release()}",
        }

    def _format_gb(self, total_bytes: int) -> str:
        if total_bytes <= 0:
            return "-"
        return f"{total_bytes / (1024 ** 3):.1f} GB"

    def _parse_size_b(self, name: str, size_text: str) -> Optional[float]:
        for text in (name, size_text):
            match = re.search(r"(\d+(?:\.\d+)?)\s*[bB]", text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None


class AssistantLoopRegistry:
    def __init__(self, builtin_paths: Optional[Sequence[Path]]=None):
        default_paths = list(builtin_paths or [DEFAULT_ASSISTANT_LOOPS_PATH])
        self.builtin_paths = [Path(path).resolve() for path in default_paths]
        self.external_paths: List[Path] = []
        self._loops: Dict[str, Dict[str, Any]] = {}
        self.loaded_sources: List[str] = []
        self.reload()

    def reload(self) -> Dict[str, Any]:
        self._loops = {}
        self.loaded_sources = []
        loaded = 0
        for path in self.builtin_paths:
            if path.exists():
                loaded += self._load_path(path)
        if loaded == 0:
            loaded += self._load_payload(self._default_payload(), "builtin_defaults")
        for path in self.external_paths:
            if path.exists():
                loaded += self._load_path(path)
        return {"ok": True, "loaded": loaded, "sources": list(self.loaded_sources)}

    def import_loop_file(self, path_like: str | Path) -> Dict[str, Any]:
        path = Path(path_like).resolve()
        if path not in self.external_paths:
            self.external_paths.append(path)
        loaded = self._load_path(path)
        return {"ok": loaded > 0, "loaded": loaded, "path": str(path)}

    def list_loops(self) -> List[Dict[str, Any]]:
        return [dict(loop) for loop in self._loops.values()]

    def get_loop(self, loop_id: str) -> Optional[Dict[str, Any]]:
        loop = self._loops.get(str(loop_id).strip())
        return dict(loop) if loop else None

    def _load_path(self, path: Path) -> int:
        payload = json.loads(path.read_text(encoding="utf-8"))
        loaded = self._load_payload(payload, str(path))
        if loaded:
            self.loaded_sources.append(str(path))
        return loaded

    def _load_payload(self, payload: Any, source: str) -> int:
        loops_payload = payload.get("loops", []) if isinstance(payload, dict) else payload
        loaded = 0
        for loop_payload in loops_payload or []:
            normalized = self._normalize_loop(loop_payload, source)
            self._loops[normalized["loop_id"]] = normalized
            loaded += 1
        return loaded

    def _normalize_loop(self, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
        loop_id = str(payload.get("loop_id") or payload.get("id") or "").strip()
        if not loop_id:
            raise ValueError(f"Loop missing loop_id in {source}")
        return {
            "loop_id": loop_id,
            "name": str(payload.get("name", loop_id)).strip() or loop_id,
            "description": str(payload.get("description", "")).strip(),
            "system_prompt": str(payload.get("system_prompt", "")).strip(),
            "final_prompt": str(payload.get("final_prompt", "")).strip(),
            "window_messages": max(1, int(payload.get("window_messages", 8) or 8)),
            "steps": list(payload.get("steps", []) or []),
            "source": source,
        }

    def _default_payload(self) -> Dict[str, Any]:
        return {
            "loops": [
                {
                    "loop_id": "direct_chat",
                    "name": "Direct Chat",
                    "description": "Plain session chat with optional selected-service grounding.",
                    "system_prompt": "You are helping a developer reason about a local microservice library. Prefer grounded answers over speculation.",
                    "final_prompt": "User request:\n{{user_prompt}}\n\nSelected service context:\n{{selected_service.pretty_json|selected_service_json}}",
                    "window_messages": 10,
                    "steps": [],
                },
                {
                    "loop_id": "library_investigation",
                    "name": "Library Investigation",
                    "description": "Search the catalog, pick the best service match, inspect it, then inspect dependencies before answering.",
                    "system_prompt": "You are a grounded library operator. Use the supplied catalog evidence and explicitly mention when the library search was ambiguous.",
                    "window_messages": 8,
                    "steps": [
                        {
                            "id": "service_search",
                            "kind": "tool",
                            "tool": "search_services",
                            "title": "Search catalog for matching services",
                            "query": "{{user_prompt}}",
                            "limit": 6,
                        },
                        {
                            "id": "service_detail",
                            "kind": "tool",
                            "tool": "describe_service",
                            "title": "Inspect the active service",
                            "service": "{{active_service_identifier}}",
                        },
                        {
                            "id": "dependency_report",
                            "kind": "tool",
                            "tool": "show_dependencies",
                            "title": "Inspect active-service dependencies",
                            "service": "{{active_service_identifier}}",
                        },
                    ],
                    "final_prompt": (
                        "User request:\n{{user_prompt}}\n\n"
                        "Active service:\n{{active_service_identifier}}\n\n"
                        "Search results:\n{{steps.service_search.pretty_json}}\n\n"
                        "Service detail:\n{{steps.service_detail.pretty_json}}\n\n"
                        "Dependencies:\n{{steps.dependency_report.pretty_json}}\n\n"
                        "Answer with concrete findings from the catalog. If there was no strong service match, say that plainly."
                    ),
                },
                {
                    "loop_id": "blueprint_advisor",
                    "name": "Blueprint Advisor",
                    "description": "Search services, then produce a starter blueprint recommendation grounded in the current catalog.",
                    "system_prompt": "You are recommending practical starter blueprints for this local library. Keep the recommendation concrete and explain why the selected services belong together.",
                    "window_messages": 6,
                    "steps": [
                        {
                            "id": "service_search",
                            "kind": "tool",
                            "tool": "search_services",
                            "title": "Search for candidate services",
                            "query": "{{user_prompt}}",
                            "limit": 5,
                        },
                        {
                            "id": "recommended_blueprint",
                            "kind": "tool",
                            "tool": "recommend_blueprint",
                            "title": "Build a starter blueprint from the active service",
                            "services": "{{active_service_identifier}}",
                            "name": "Operator Draft",
                        },
                    ],
                    "final_prompt": (
                        "User request:\n{{user_prompt}}\n\n"
                        "Active service:\n{{active_service_identifier}}\n\n"
                        "Search results:\n{{steps.service_search.pretty_json}}\n\n"
                        "Recommended blueprint:\n{{steps.recommended_blueprint.pretty_json}}\n\n"
                        "Explain the recommendation, call out assumptions, and mention any obvious services that might need to be added."
                    ),
                },
            ]
        }


class AssistantLoopRunner:
    def __init__(self, query_service: Any, assistant_service: Optional[OllamaAssistantService]=None):
        self.query_service = query_service
        self.assistant_service = assistant_service or OllamaAssistantService()

    def run_loop(
        self,
        loop_spec: Dict[str, Any],
        user_prompt: str,
        model_name: str="",
        selected_service: Optional[Dict[str, Any]]=None,
        chat_history: Optional[Sequence[Dict[str, str]]]=None,
    ) -> Dict[str, Any]:
        selected = dict(selected_service or {})
        context: Dict[str, Any] = {
            "user_prompt": user_prompt,
            "selected_service": self._augment_value(selected) if selected else {},
            "selected_service_json": json.dumps(selected, indent=2) if selected else "{}",
            "active_service_identifier": selected.get("class_name") or selected.get("service_name") or "",
            "steps": {},
        }
        steps_output: Dict[str, Any] = {}
        trace: List[Dict[str, Any]] = []
        for index, raw_step in enumerate(loop_spec.get("steps", []), start=1):
            rendered_step = self._render_value(raw_step, context)
            step_id = str(rendered_step.get("id") or f"step_{index}").strip()
            step_kind = str(rendered_step.get("kind", "tool")).strip() or "tool"
            trace_item: Dict[str, Any] = {
                "step_id": step_id,
                "title": rendered_step.get("title") or step_id,
                "kind": step_kind,
                "status": "completed",
            }
            if step_kind == "tool":
                tool_name = str(rendered_step.get("tool", "")).strip()
                trace_item["tool"] = tool_name
                tool_output = self._execute_tool(tool_name, rendered_step, context)
                steps_output[step_id] = tool_output
                context["steps"][step_id] = self._augment_value(tool_output)
                self._update_active_service_identifier(context, tool_name, tool_output)
                trace_item["summary"] = self._summarize_step_output(tool_output)
                trace_item["output"] = tool_output
            else:
                note = str(rendered_step.get("note", "")).strip()
                trace_item["summary"] = note
                trace_item["output"] = {"note": note}
            trace.append(trace_item)

        system_prompt = self._render_template(loop_spec.get("system_prompt", ""), context)
        final_prompt = self._render_template(loop_spec.get("final_prompt", "{{user_prompt}}"), context)
        grounding = {
            "loop": {
                "loop_id": loop_spec.get("loop_id", ""),
                "name": loop_spec.get("name", ""),
                "description": loop_spec.get("description", ""),
                "source": loop_spec.get("source", ""),
            },
            "selected_service": selected,
            "active_service_identifier": context.get("active_service_identifier", ""),
            "steps": steps_output,
            "tasklist": [self._trace_to_task(item) for item in trace],
        }
        assistant_reply, model_result = self._resolve_assistant_reply(
            loop_spec=loop_spec,
            user_prompt=user_prompt,
            model_name=model_name,
            system_prompt=system_prompt,
            final_prompt=final_prompt,
            grounding=grounding,
            chat_history=chat_history or [],
        )
        return {
            "ok": bool(str(assistant_reply).strip()),
            "loop": dict(loop_spec),
            "assistant_output": assistant_reply,
            "model_result": model_result,
            "steps": steps_output,
            "trace": trace,
            "tasklist": grounding["tasklist"],
            "grounding_context": grounding,
            "active_service_identifier": context.get("active_service_identifier", ""),
            "system_prompt": system_prompt,
            "final_prompt": final_prompt,
            "max_history_messages": max(1, int(loop_spec.get("window_messages", 8) or 8)),
        }

    def _resolve_assistant_reply(
        self,
        loop_spec: Dict[str, Any],
        user_prompt: str,
        model_name: str,
        system_prompt: str,
        final_prompt: str,
        grounding: Dict[str, Any],
        chat_history: Sequence[Dict[str, str]],
    ) -> tuple[str, Dict[str, Any]]:
        fallback = self._deterministic_summary(loop_spec, user_prompt, grounding)
        if not str(model_name).strip():
            return fallback, {"ok": True, "error": "", "output": fallback, "used_fallback": True}
        messages = list(chat_history) + [{"role": "user", "content": final_prompt}]
        model_result = self.assistant_service.chat(
            model_name=model_name,
            messages=messages,
            system_prompt=system_prompt,
            context=grounding,
            max_history_messages=int(loop_spec.get("window_messages", 8) or 8),
        )
        output = str(model_result.get("output", "")).strip()
        if model_result.get("ok") and output:
            model_result["used_fallback"] = False
            return output, model_result
        error_text = str(model_result.get("error", "")).strip() or "Assistant response was empty."
        fallback_output = f"{fallback}\n\nModel fallback reason: {error_text}"
        model_result["output"] = fallback_output
        model_result["used_fallback"] = True
        return fallback_output, model_result

    def _execute_tool(self, tool_name: str, step: Dict[str, Any], context: Dict[str, Any]) -> Any:
        if tool_name == "list_services":
            layer = self._clean_optional_text(step.get("layer"))
            return self.query_service.list_services(layer=layer or None)
        if tool_name == "search_services":
            return self._search_services(
                query=str(step.get("query", "")).strip(),
                layer=self._clean_optional_text(step.get("layer")),
                limit=self._coerce_int(step.get("limit"), default=6),
            )
        if tool_name == "describe_service":
            identifier = self._resolve_service_identifier(step, context)
            return self.query_service.describe_service(identifier) if identifier else {}
        if tool_name == "show_dependencies":
            identifier = self._resolve_service_identifier(step, context)
            return self.query_service.show_dependencies(identifier) if identifier else {}
        if tool_name == "list_templates":
            return self.query_service.list_templates()
        if tool_name == "list_orchestrators":
            return self.query_service.list_orchestrators()
        if tool_name == "list_managers":
            return self.query_service.list_managers()
        if tool_name == "show_ui_components":
            return self.query_service.show_ui_components()
        if tool_name == "template_blueprint":
            return self.query_service.template_blueprint(
                str(step.get("template_id", "")).strip(),
                destination=str(step.get("destination", "")).strip(),
                name=str(step.get("name", "")).strip(),
                vendor_mode=self._clean_optional_text(step.get("vendor_mode")),
                resolution_profile=self._clean_optional_text(step.get("resolution_profile")),
            )
        if tool_name == "recommend_blueprint":
            services = self._coerce_service_list(step.get("services"), context)
            return self.query_service.recommend_blueprint(
                services,
                destination=str(step.get("destination", "")).strip(),
                name=str(step.get("name", "Assistant Draft")).strip(),
                vendor_mode=str(step.get("vendor_mode", "module_ref")).strip() or "module_ref",
                resolution_profile=str(step.get("resolution_profile", "app_ready")).strip() or "app_ready",
            )
        raise KeyError(f"Unsupported assistant tool: {tool_name}")

    def _search_services(self, query: str, layer: Optional[str], limit: int) -> Dict[str, Any]:
        services = self.query_service.list_services(layer=layer or None)
        normalized_query = query.strip().lower()
        tokens = [token for token in re.findall(r"[a-z0-9_]+", normalized_query) if token]
        matches: List[Dict[str, Any]] = []
        for service in services:
            haystacks = {
                "class_name": str(service.get("class_name", "")).lower(),
                "service_name": str(service.get("service_name", "")).lower(),
                "description": str(service.get("description", "")).lower(),
                "layer": str(service.get("layer", "")).lower(),
                "import_key": str(service.get("import_key", "")).lower(),
                "source_path": str(service.get("source_path", "")).lower(),
                "tags": " ".join(str(item).lower() for item in service.get("tags", [])),
                "capabilities": " ".join(str(item).lower() for item in service.get("capabilities", [])),
            }
            combined = " ".join(haystacks.values())
            score = 0
            if not tokens and not normalized_query:
                score = 1
            if normalized_query and normalized_query in {haystacks["class_name"], haystacks["service_name"]}:
                score += 100
            if normalized_query and normalized_query in combined:
                score += 20
            for token in tokens:
                if token == haystacks["layer"]:
                    score += 8
                if token in haystacks["class_name"]:
                    score += 12
                if token in haystacks["service_name"]:
                    score += 10
                if token in haystacks["tags"]:
                    score += 6
                if token in haystacks["capabilities"]:
                    score += 6
                if token in haystacks["description"]:
                    score += 3
                if token in haystacks["import_key"] or token in haystacks["source_path"]:
                    score += 2
            if score <= 0:
                continue
            matches.append(
                {
                    "score": score,
                    "class_name": service.get("class_name", ""),
                    "service_name": service.get("service_name", ""),
                    "layer": service.get("layer", ""),
                    "description": service.get("description", ""),
                    "tags": list(service.get("tags", [])),
                    "capabilities": list(service.get("capabilities", [])),
                    "import_key": service.get("import_key", ""),
                    "source_path": service.get("source_path", ""),
                }
            )
        matches.sort(key=lambda item: (-int(item["score"]), item["layer"], item["class_name"]))
        return {
            "query": query,
            "layer": layer or "all",
            "matches": matches[: max(1, limit)],
            "total_matches": len(matches),
        }

    def _resolve_service_identifier(self, step: Dict[str, Any], context: Dict[str, Any]) -> str:
        explicit = str(step.get("service", "")).strip()
        if explicit:
            return explicit
        return str(context.get("active_service_identifier", "")).strip()

    def _coerce_service_list(self, value: Any, context: Dict[str, Any]) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "").strip()
        if not text:
            active = str(context.get("active_service_identifier", "")).strip()
            return [active] if active else []
        return [item.strip() for item in re.split(r"[\n,]+", text) if item.strip()]

    def _clean_optional_text(self, value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    def _coerce_int(self, value: Any, default: int) -> int:
        try:
            return max(1, int(value))
        except Exception:
            return default

    def _update_active_service_identifier(self, context: Dict[str, Any], tool_name: str, output: Any) -> None:
        if str(context.get("active_service_identifier", "")).strip():
            return
        if tool_name == "search_services":
            matches = output.get("matches", []) if isinstance(output, dict) else []
            if matches:
                context["active_service_identifier"] = matches[0].get("class_name", "") or matches[0].get("service_name", "")
                return
        if isinstance(output, dict):
            identifier = output.get("class_name") or output.get("service_name")
            if identifier:
                context["active_service_identifier"] = identifier
            elif isinstance(output.get("service"), dict):
                service = output["service"]
                context["active_service_identifier"] = service.get("class_name") or service.get("service_name") or ""

    def _render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: self._render_value(item, context) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render_value(item, context) for item in value]
        if isinstance(value, str):
            return self._render_template(value, context)
        return value

    def _render_template(self, template: str, context: Dict[str, Any]) -> str:
        if "{{" not in template:
            return template

        def replace(match: re.Match[str]) -> str:
            expression = match.group(1).strip()
            resolved = self._resolve_expression(expression, context)
            if isinstance(resolved, (dict, list)):
                return json.dumps(resolved, indent=2)
            return "" if resolved is None else str(resolved)

        return re.sub(r"\{\{\s*(.*?)\s*\}\}", replace, template)

    def _resolve_expression(self, expression: str, context: Dict[str, Any]) -> Any:
        for candidate in [item.strip() for item in expression.split("|") if item.strip()]:
            value = self._resolve_path(context, candidate)
            if value not in (None, "", [], {}):
                return value
        return ""

    def _resolve_path(self, value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
                continue
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except Exception:
                    return None
                continue
            return None
        return current

    def _augment_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            augmented = {key: self._augment_value(item) for key, item in value.items()}
            augmented.setdefault("pretty_json", json.dumps(value, indent=2))
            return augmented
        if isinstance(value, list):
            return [self._augment_value(item) for item in value]
        return value

    def _summarize_step_output(self, output: Any) -> str:
        if isinstance(output, dict):
            if "total_matches" in output:
                return f"{output.get('total_matches', 0)} matches"
            if output.get("class_name"):
                return f"Resolved {output.get('class_name')}"
            if isinstance(output.get("service"), dict):
                service = output["service"]
                return f"Dependencies for {service.get('class_name') or service.get('service_name')}"
            if output.get("name"):
                return str(output.get("name"))
        if isinstance(output, list):
            return f"{len(output)} items"
        return str(output)[:120]

    def _trace_to_task(self, trace_item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "step_id": trace_item.get("step_id", ""),
            "title": trace_item.get("title", ""),
            "status": trace_item.get("status", "completed"),
            "summary": trace_item.get("summary", ""),
            "tool": trace_item.get("tool", ""),
        }

    def _deterministic_summary(
        self,
        loop_spec: Dict[str, Any],
        user_prompt: str,
        grounding: Dict[str, Any],
    ) -> str:
        lines = [
            f"Loop: {loop_spec.get('name', loop_spec.get('loop_id', 'Assistant Loop'))}",
            f"Request: {user_prompt}",
        ]
        active_service = str(grounding.get("active_service_identifier", "")).strip()
        if active_service:
            lines.append(f"Active service: {active_service}")
        steps = grounding.get("steps", {})
        search = steps.get("service_search", {}) if isinstance(steps, dict) else {}
        if isinstance(search, dict) and search.get("matches"):
            top = search["matches"][0]
            lines.append(
                "Top match: "
                + str(top.get("class_name") or top.get("service_name") or "(unknown)")
                + f" [{top.get('layer', '-')}]"
            )
        detail = steps.get("service_detail", {}) if isinstance(steps, dict) else {}
        if isinstance(detail, dict) and detail.get("description"):
            lines.append("Summary: " + str(detail.get("description", "")).strip())
        deps = steps.get("dependency_report", {}) if isinstance(steps, dict) else {}
        if isinstance(deps, dict):
            code_count = len(deps.get("code_dependencies", []))
            runtime_count = len(deps.get("runtime_dependencies", []))
            external_count = len(deps.get("external_dependencies", []))
            if code_count or runtime_count or external_count:
                lines.append(f"Dependencies: code={code_count}, runtime={runtime_count}, external={external_count}")
        lines.append("This response is the built-in fallback summary because no model reply was available.")
        return "\n".join(lines)
