import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";

const MESSAGE =
  "No direct `python3`. Use `uv run` instead. For one-off dependencies, use `uv run --with`.";

function usesBarePython3(command: string): boolean {
  // Matches likely shell command invocations of python3, while allowing
  // `uv run python3 ...`.
  const barePython3 = /(^|[;&|()\s])python3(\s|$)/;
  const uvRunPython3 = /(^|[;&|()\s])uv\s+run\s+python3(\s|$)/;
  return barePython3.test(command) && !uvRunPython3.test(command);
}

export default function (pi: ExtensionAPI) {
  // Reject agent bash tool calls that invoke bare python3.
  pi.on("tool_call", (event) => {
    if (!isToolCallEventType("bash", event)) return;

    if (usesBarePython3(event.input.command)) {
      return { block: true, reason: MESSAGE };
    }
  });

  // Reject user-entered ! / !! bash commands that invoke bare python3.
  pi.on("user_bash", (event) => {
    if (!usesBarePython3(event.command)) return;

    return {
      result: {
        output: MESSAGE,
        exitCode: 1,
        cancelled: false,
        truncated: false,
      },
    };
  });
}
