/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1400px'
      }
    },
    extend: {
      fontFamily: {
        // Attest primary font
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        // shadcn-vue semantic tokens (mapped to Attest palette via CSS vars)
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        sidebar: {
          DEFAULT: 'hsl(var(--sidebar-background))',
          foreground: 'hsl(var(--sidebar-foreground))',
          primary: 'hsl(var(--sidebar-primary))',
          'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
          accent: 'hsl(var(--sidebar-accent))',
          'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
          border: 'hsl(var(--sidebar-border))',
          ring: 'hsl(var(--sidebar-ring))'
        },
        // Attest raw palette — available as Tailwind utilities
        // e.g. bg-attest-teal-70, text-attest-grey-900
        attest: {
          grey: {
            50:   '#fafafa',
            100:  '#f5f5f5',
            200:  '#eaebeb',
            300:  '#e1e2e2',
            400:  '#c2c2c2',
            500:  '#b3b5b5',
            600:  '#8b8d8d',
            700:  '#6e6f6f',
            800:  '#4c4c4c',
            900:  '#2d2d2d',
            1000: '#191919',
          },
          teal: {
            10: '#f1f6f6',
            20: '#e2eef1',
            30: '#cfe6ec',
            40: '#99c9d7',
            50: '#81bdce',
            60: '#2f98b1',
            70: '#00829b',
            80: '#195260',
            90: '#183037',
          },
          red: {
            10: '#faf5f4',
            20: '#f8e7e3',
            60: '#eb6044',
            70: '#ce361c',
            80: '#8f2512',
          },
          green: {
            10: '#eef7f3',
            20: '#ddf0e7',
            60: '#429d69',
            70: '#1b7c4a',
          },
          firecracker: {
            30: '#efdfcd',
            60: '#de6c2b',
            70: '#af5623',
            DEFAULT: '#f7622b',
          },
          yellow: {
            10: '#fcf6e2',
            40: '#f6b744',
            70: '#a85b00',
          },
          blue: {
            10: '#eaf9ff',
            40: '#9cc6f1',
            70: '#006ae4',
            80: '#003dc2',
          },
          berry: {
            10: '#f8f5f6',
            40: '#ddb7c8',
            70: '#b54681',
            80: '#940460',
          },
        },
      },
      borderRadius: {
        // Attest uses 4px base radius
        lg: 'var(--radius)',             /* 4px   */
        md: 'var(--radius)',             /* 4px   */
        sm: 'calc(var(--radius) / 2)',   /* 2px   */
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--reka-accordion-content-height)' }
        },
        'accordion-up': {
          from: { height: 'var(--reka-accordion-content-height)' },
          to: { height: '0' }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
}
