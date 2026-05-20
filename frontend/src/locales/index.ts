import en from "./en.json";
import nl from "./nl.json";

const locales: Record<string, Record<string, string>> = { en, nl };

let currentLocale = "en";

export function setLocale(locale: string) {
  currentLocale = locale in locales ? locale : "en";
}

export function t(key: string): string {
  return locales[currentLocale]?.[key] ?? locales.en[key] ?? key;
}
