import { describe, expect, test, vi } from "vitest";

import pluginManifest from "../openclaw.plugin.json";
import { registerViaApi, type OpenClawPluginApiLike } from "../src/index";

const CONFIG = {
  apiUrl: "https://panel.example.com:8080/remote/json.php",
  username: "admin",
  password: "test-password",
};

describe("OpenClaw native tool registration", () => {
  test("registers every manifest tool using the current AgentTool shape", async () => {
    const tools: Parameters<OpenClawPluginApiLike["registerTool"]>[0][] = [];
    const registerCommand = vi.fn();

    registerViaApi({
      pluginConfig: CONFIG,
      registerTool: (tool) => tools.push(tool),
      registerCommand,
    });

    expect(tools).toHaveLength(pluginManifest.contracts.tools.length);
    expect(registerCommand).toHaveBeenCalledTimes(1);
    const command = registerCommand.mock.calls[0][0] as { handler: () => Promise<{ text: string }> };
    await expect(command.handler()).resolves.toMatchObject({
      text: expect.stringContaining("💡 *Examples*"),
    });
    for (const tool of tools) {
      expect(tool.label).toBe(tool.name);
      expect(tool.parameters).toMatchObject({ type: "object" });
      expect(tool.execute).toBeTypeOf("function");
    }
  });
});
