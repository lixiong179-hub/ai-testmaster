const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    setupNodeEvents(on, config) {
      return config
    },
  },
  video: false,
  screenshotOnRunFailure: true,
  chromeWebSecurity: false,
})
