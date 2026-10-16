/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: '#0A0B0E',
          panel: '#101217',
          elevated: '#161921',
          card: '#1A1E28',
          border: 'rgba(255, 255, 255, 0.075)',
          accent: '#D97757',
          accentHover: '#E4886A',
          emerald: '#10B981',
          amber: '#F59E0B',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Cascadia Code"', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
