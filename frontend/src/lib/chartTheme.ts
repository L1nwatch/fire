function cssVar(name: string, fallback: string) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

export function chartThemeColors() {
  return {
    accent: cssVar('--accent', '#1f7a63'),
    orange: cssVar('--orange', '#d97432'),
    blue: cssVar('--blue', '#2f6f9f'),
    violet: cssVar('--violet', '#6f5bb8'),
    text: cssVar('--muted', '#68716d'),
    ink: cssVar('--ink', '#1f2522'),
    line: cssVar('--line', '#d9dfda'),
    surface: cssVar('--surface', '#ffffff'),
  }
}
