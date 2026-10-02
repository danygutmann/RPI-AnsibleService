const themeToggle = document.getElementById("themeToggle");

function updateThemeButton() {
  const dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
  themeToggle.textContent = dark ? "☀ Hell" : "◐ Dunkel";
  themeToggle.setAttribute("aria-pressed", String(dark));
  themeToggle.setAttribute(
    "aria-label",
    dark ? "Helles Design einschalten" : "Dunkles Design einschalten"
  );
}

themeToggle.addEventListener("click", () => {
  const dark = document.documentElement.getAttribute("data-bs-theme") === "dark";
  const nextTheme = dark ? "light" : "dark";

  document.documentElement.setAttribute("data-bs-theme", nextTheme);
  try {
    localStorage.setItem("ansible-theme", nextTheme);
  } catch (_) {}
  updateThemeButton();
});

updateThemeButton();