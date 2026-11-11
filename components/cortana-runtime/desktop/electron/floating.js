document.getElementById("toggle").addEventListener("click", () => window.cortana.toggle());
document.getElementById("screen").addEventListener("click", async () => {
  const button = document.getElementById("screen");
  button.disabled = true;
  try { await window.cortana.quickScreen(); }
  catch (error) { button.title = error.message; }
  finally { button.disabled = false; }
});
