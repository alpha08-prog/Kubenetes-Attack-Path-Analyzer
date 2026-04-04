import { Moon, Sun } from "lucide-react"
import { useTheme } from "./theme-provider"

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  const toggleTheme = () => {
    if (theme === 'light') {
      setTheme('dark')
    } else if (theme === 'dark') {
      setTheme('system')
    } else {
      setTheme('light')
    }
  }

  return (
    <button
      onClick={toggleTheme}
      title={`Current theme: ${theme}. Click to toggle.`}
      className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-secondary hover:bg-surface-hover text-foreground transition-colors overflow-hidden"
    >
      <Sun className={`absolute w-4 h-4 transition-all ${theme === 'dark' ? '-translate-y-10 opacity-0' : 'translate-y-0 opacity-100'} ${theme === 'system' ? 'text-primary' : ''}`} />
      <Moon className={`absolute w-4 h-4 transition-all ${theme === 'light' ? 'translate-y-10 opacity-0' : 'translate-y-0 opacity-100'} ${theme === 'system' ? 'text-primary' : ''}`} />
      
      {/* System indicator dot when system theme is active */}
      {theme === 'system' && (
        <span className="absolute bottom-1 right-1 w-1.5 h-1.5 rounded-full bg-primary" />
      )}
    </button>
  )
}
