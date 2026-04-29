module.exports = {
  root: true,
  env: {
    node: true,
  },
  extends: ['eslint:recommended', '@vue/eslint-config-typescript', '@vue/eslint-config-prettier'],
  parserOptions: {
    ecmaVersion: 2020,
  },
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'prettier/prettier': [
      'error',
      {
        singleQuote: true,
        semi: false,
        tabWidth: 2,
        trailingComma: 'es5',
      },
    ],
  },
}
