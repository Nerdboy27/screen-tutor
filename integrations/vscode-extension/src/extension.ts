import * as vscode from "vscode";

type Reply = { session_id: string; turn: { text: string } };

let sessionId: string | null = null;

function config() {
  const settings = vscode.workspace.getConfiguration("screenTutor");
  return {
    baseUrl: settings.get<string>("apiBaseUrl", "http://127.0.0.1:8000"),
    apiKey: settings.get<string>("apiKey", ""),
  };
}

async function post(path: string, body: unknown): Promise<Reply> {
  const { baseUrl, apiKey } = config();
  const headers: Record<string, string> = { "content-type": "application/json" };
  if (apiKey) headers["x-api-key"] = apiKey;

  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Tutor API ${response.status}: ${await response.text()}`);
  }
  return (await response.json()) as Reply;
}

function show(text: string) {
  const channel = vscode.window.createOutputChannel("AI Tutor", "markdown");
  channel.appendLine(text);
  channel.show(true);
}

/**
 * Sends the editor selection (or whole document) as a text follow-up. The IDE
 * has no screen capture, so it reuses the session's existing visual context
 * when one is active.
 */
async function explainSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Open a file first.");
    return;
  }
  const selection = editor.selection.isEmpty
    ? editor.document.getText()
    : editor.document.getText(editor.selection);
  const language = editor.document.languageId;
  const prompt = `Explain this ${language} code:\n\n\`\`\`${language}\n${selection}\n\`\`\``;

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: "AI Tutor" },
    async () => {
      if (!sessionId) {
        const created = await fetch(`${config().baseUrl}/sessions`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ title: "VS Code", client: "vscode" }),
        });
        sessionId = ((await created.json()) as { id: string }).id;
      }
      const reply = await post(`/sessions/${sessionId}/follow-up`, {
        prompt,
        source: "vscode",
      });
      sessionId = reply.session_id;
      show(reply.turn.text);
    },
  );
}

async function followUp() {
  if (!sessionId) {
    vscode.window.showWarningMessage("Run 'Explain selection' first.");
    return;
  }
  const prompt = await vscode.window.showInputBox({ prompt: "Ask the tutor" });
  if (!prompt) return;
  const reply = await post(`/sessions/${sessionId}/follow-up`, {
    prompt,
    source: "vscode",
  });
  show(reply.turn.text);
}

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("screenTutor.explainSelection", explainSelection),
    vscode.commands.registerCommand("screenTutor.followUp", followUp),
  );
}

export function deactivate() {
  sessionId = null;
}
