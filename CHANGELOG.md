# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Versioning Policy

| Change type | Version bump | Example |
|-------------|-------------|---------|
| New public class, function, or protocol | **minor** | `1.3.x` → `1.4.0` |
| Bug fix, internal refactor (no API change) | **patch** | `1.3.2` → `1.3.3` |
| Breaking change to public API | **major** | `1.x.y` → `2.0.0` |

A "public API" is anything importable from `agentica` top-level `__init__.py`.

---

## [Unreleased]

### Added
- `SandboxConfig.allowed_commands` — optional command whitelist for `execute` tool (prefix-matched on first token)
- `Agent._running` flag — concurrent reuse of the same Agent instance now logs a warning
- `WorkingMemory.max_messages` — soft FIFO eviction limit (default: 200) to prevent unbounded memory growth
- `Message.role` field validator — rejects invalid roles at construction time (`system`, `user`, `assistant`, `tool` only)

### Fixed
- `update_model()` now clears `model.functions` and `model.tools` before each run, preventing tool accumulation on reused Agent instances
- `OpenAIChat.response()` raises `ValueError` instead of `IndexError` when `choices` is empty
- `AnthropicChat.response()` raises `ValueError` instead of crashing when `content` is empty
- `FunctionCall.execute()` generator result concatenation now uses `str(item)` to prevent `TypeError` on non-string generators
- `OpenAILike` warns at construction time when `api_key` is still the placeholder `"not-provided"`
- `_load_mcp_tools` removed redundant `if/else` branch (both branches were identical)
- `task()` recursion depth capped at 5 levels via `_task_depth` context propagation

### Added (Tests)
- `tests/test_hooks.py` — AgentHooks, RunHooks, `_CompositeRunHooks`, ConversationArchiveHooks
- `tests/test_runner.py` — empty message guard, concurrent warning, run_timeout, structured output fallback
- `tests/test_swarm.py` — parallel mode, partial failure, duplicate name detection
- `tests/test_model_validation.py` — empty choices, usage=None, Message role validator, structured output fallback

---

## [1.3.2] — 2026-03-17

### Added
- `Swarm` — multi-agent parallel autonomous collaboration (`agentica/swarm.py`)
- `ConversationArchiveHooks` — auto-archives conversations to workspace after each run
- `_CompositeRunHooks` — internal wrapper for composing multiple `RunHooks` instances
- `RunConfig.enabled_tools` / `enabled_skills` — per-run tool/skill whitelisting
- `Agent.disable_tool()` / `enable_tool()` / `disable_skill()` / `enable_skill()` — agent-level runtime control
- `Agent._load_runtime_config()` — loads tool/skill enable/disable from `.agentica/runtime_config.yaml`
- `SandboxConfig.blocked_commands` — command-level blacklist for `execute` tool
- `examples/agent_patterns/08_swarm.py` — Swarm usage example
- `examples/agent_patterns/09_runtime_config.py` — Runtime config example
- `examples/agent_patterns/10_subagent_demo.py` — SubAgent example

### Changed
- `deep_agent.py` renamed to `tools/buildin_tools.py`; `DeepAgent` now uses `BuiltinFileTool`, `BuiltinExecuteTool`, `BuiltinWebSearchTool` etc.
- `Runner._run_impl` — removed duplicate auto-archive logic; archive is now handled exclusively by `ConversationArchiveHooks`

---

## [1.3.1] — 2026-03 (v3 post-merge cleanup)

### Added
- `WebSearchAgent` with search enhancement modules (`search/orchestrator.py`, `query_decomposer.py`, `evidence_store.py`, `answer_verifier.py`)
- Extended thinking support for Claude and KimiChat models
- Kimi provider integration (`model/kimi/`)

### Fixed
- Preserve tool call messages in multi-turn conversation history
- Deduplicate Model layer, unify `RunConfig` signatures

---

## [1.3.0] — 2026-03 (v3 architecture refactor)

### Changed (Breaking — internal architecture, public API preserved)
- **Phase 1**: Removed 19 thin provider directories; unified via `model/providers.py` registry factory
- **Phase 2**: Converted `Model` hierarchy from Pydantic `BaseModel` to `@dataclass`
- **Phase 3**: Async interface consistency + structured output for all providers
- **Phase 4**: Added `@tool` decorator and global tool registry (`tools/registry.py`)
- **Phase 5**: Extracted `Runner` from `RunnerMixin`; `Agent` now delegates execution via `self._runner`
- **Phase 6**: Unified guardrails with `core.py` abstraction layer
- **Phase 7**: Simplified `__init__.py` lazy loading
- **Phase 8**: 35 new v3 tests

### Added
- `AgentHooks`, `RunHooks` lifecycle hooks system
- `RunConfig` per-run configuration overrides
- `SubAgent` for isolated ephemeral task delegation
- Skill system (`skills/`) — Markdown+YAML frontmatter skill injection
- ACP server for IDE integration (Zed, JetBrains)

---

## [1.2.x] and earlier

See git log for historical changes prior to the v3 refactor.
