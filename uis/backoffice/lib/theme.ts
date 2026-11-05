export const THEME_STORAGE_KEY = 'nexova_theme';
const THEME_CHANGE_EVENT = 'nexova-theme-change';

export type Theme = 'light' | 'dark';

export const themeInitScript = `
  (() => {
    let theme;
    try {
      theme = localStorage.getItem('${THEME_STORAGE_KEY}');
    } catch (error) {
      console.warn('No se pudo leer la preferencia de tema:', error);
    }
    document.documentElement.dataset.theme = theme === 'light' || theme === 'dark'
      ? theme
      : (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  })();
`;

export function getTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

export function getServerTheme(): Theme {
  return 'light';
}

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (error) {
    console.warn('No se pudo guardar la preferencia de tema:', error);
  }
  window.dispatchEvent(new Event(THEME_CHANGE_EVENT));
}

export function subscribeToTheme(onChange: () => void) {
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function syncTheme() {
    let stored;
    try {
      stored = localStorage.getItem(THEME_STORAGE_KEY);
    } catch (error) {
      console.warn('No se pudo leer la preferencia de tema:', error);
    }
    document.documentElement.dataset.theme = stored === 'light' || stored === 'dark'
      ? stored
      : (media.matches ? 'dark' : 'light');
    onChange();
  }

  function handleStorage(event: StorageEvent) {
    if (event.key === THEME_STORAGE_KEY || event.key === null) syncTheme();
  }

  window.addEventListener(THEME_CHANGE_EVENT, onChange);
  window.addEventListener('storage', handleStorage);
  media.addEventListener('change', syncTheme);
  return () => {
    window.removeEventListener(THEME_CHANGE_EVENT, onChange);
    window.removeEventListener('storage', handleStorage);
    media.removeEventListener('change', syncTheme);
  };
}
