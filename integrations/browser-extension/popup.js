const button = document.getElementById("capture");
const promptInput = document.getElementById("prompt");
const reply = document.getElementById("reply");

button.addEventListener("click", async () => {
  button.disabled = true;
  reply.textContent = "Thinking…";
  const response = await chrome.runtime.sendMessage({
    type: "capture",
    prompt: promptInput.value.trim() || null,
  });
  reply.textContent = response.ok ? response.body.turn.text : response.error;
  button.disabled = false;
});
