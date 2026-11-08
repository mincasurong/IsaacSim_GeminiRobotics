# DESIGN.md — IsaacSim × Gemini Cloud (Enterprise Physical AI Ops Console)

## 0. Research Log
- **`ui-ux-pro-max` Design System Query**: `python scripts/search.py "AI robotics cloud telemetry SaaS ops console dashboard" --design-system --density 8 -p "IsaacSim Gemini Cloud"` -> Selected high-density (`8/10`) SaaS dashboard tokens (`Primary #2563EB`, `Accent #5E6AD2`, `Plus Jakarta Sans` + `Inter Variable` + `JetBrains Mono`, 4.5:1+ WCAG contrast, SVG Lucide icons only, zero emoji icons in controls).
- **Layer A & Layer B References**: `linear.app.md` (Obsidian dark-mode-native hierarchy `#08090a` -> `#0d0f12` -> `#14171f`, `rgba(255,255,255,0.07)` hairline borders, `"cv01", "ss03"` OpenType features, weight 510/600 hierarchy) + `redesign-skill.md` (`font-variant-numeric: tabular-nums` on all telemetry/token counters, subtle elevation, active press states, zero coloured side-border stripes).

## 1. Surface & Color Tokens
| Token | Dark Mode (Obsidian Console) | Light Mode (Enterprise Slate) | Role |
|---|---|---|---|
| `bg` | `#08090a` | `#f8fafc` | Root application canvas |
| `bgChat` | `#0c0e12` | `#ffffff` | Primary workspace / command stream surface |
| `bgSide` | `#101318` | `#f1f5f9` | Navigation header, dock, and inspector panels |
| `bgInput` | `#151921` | `#ffffff` | Control inputs, selects, and elevated cards |
| `bgHover` | `#1c212b` | `#e2e8f0` | Interactive hover wash |
| `border` | `rgba(255, 255, 255, 0.07)` | `#e2e8f0` | Default 1px structural hairline |
| `borderHi` | `rgba(255, 255, 255, 0.15)` | `#cbd5e1` | Emphasized / focused control border |
| `text` | `#f7f8f8` | `#0f172a` | Primary high-contrast foreground |
| `textDim` | `#94a3b8` | `#475569` | Secondary labels and descriptions |
| `textMuted` | `#64748b` | `#64748b` | Metadata, timestamps, and axis ticks |
| `accent` | `#5e6ad2` | `#4f46e5` | Primary brand indigo |
| `blue` | `#2563eb` | `#2563eb` | Active execution & primary CTA |
| `green` | `#10b981` | `#059669` | Connected / verified status |
| `yellow` | `#f59e0b` | `#d97706` | Queued / warning status |
| `red` | `#ef4444` | `#dc2626` | Fault / stop action |

## 2. Typography & Numeric Discipline
- **UI Sans**: `'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif` with `font-feature-settings: "cv01", "ss03"`.
- **Telemetry & Code Mono**: `'JetBrains Mono', 'Berkeley Mono', ui-monospace, SFMono-Regular, Menlo, monospace` with `font-variant-numeric: tabular-nums`.
- **Iconography**: Strictly SVG Lucide icons (`strokeWidth={1.75}`) across all navigation tabs, toolbar buttons, mode switches, and prompt chips.
