module.exports = {
  content: [
    "./frontend/templates/**/*.html",
    "./subscriptions/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#f0f1f5', 100: '#d9dbe5', 200: '#b3b7cb', 300: '#8d93b1',
          400: '#676f97', 500: '#414b7d', 600: '#1e2937', 700: '#0f172a',
          800: '#0a0f1c', 900: '#05080e',
        },
        gold: {
          50: '#fdf9ed', 100: '#f9f0c8', 200: '#f3e193', 300: '#edd25e',
          400: '#e8c76b', 500: '#d4af37', 600: '#b8962f', 700: '#9c7d28',
          800: '#806421', 900: '#644b1a',
        },
        cream: { 50: '#fdfcf9', 100: '#f7f4ec', 200: '#efeadd', 300: '#e7e0ce' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}