const toggle = document.getElementById("shared-navigation-toggle");
const navigation = document.getElementById("shared-navigation");
const compact = globalThis.matchMedia?.("(max-width: 64rem)");

if (toggle && navigation && compact) {
  function setOpen(open) {
    const value = Boolean(open && compact.matches);
    document.body.classList.toggle("navigation-open", value);
    toggle.setAttribute("aria-expanded", String(value));
    toggle.textContent = value ? "Close menu" : "Menu";
    navigation.inert = compact.matches && !value;
  }

  toggle.addEventListener("click", () => setOpen(!document.body.classList.contains("navigation-open")));
  navigation.addEventListener("click", event => {
    if (event.target instanceof Element && event.target.closest("a")) setOpen(false);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") setOpen(false);
  });
  compact.addEventListener?.("change", () => setOpen(false));
  setOpen(false);
}
