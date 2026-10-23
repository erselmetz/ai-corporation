const themeKey = "ersel-chat-theme-v1";

export function applyStoredTheme(documentRef = document, storage) {
  let theme = "dark";
  try {
    const localStorage = storage === undefined ? globalThis.localStorage : storage;
    theme = localStorage?.getItem(themeKey) === "light" ? "light" : "dark";
  }
  catch { /* Private browsing may block local storage. */ }
  documentRef.documentElement.dataset.theme = theme;
  documentRef.body.dataset.theme = theme;
  return theme;
}

if (typeof document !== "undefined") applyStoredTheme();
