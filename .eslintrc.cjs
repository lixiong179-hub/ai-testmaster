module.exports = {
  root: true,
  env: {
    node: true,
  },
  ignorePatterns: ['dist/**', 'src/backup/**', 'coverage/**'],
  extends: ['eslint:recommended', '@vue/eslint-config-typescript', '@vue/eslint-config-prettier'],
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 'latest',
    sourceType: 'module',
    extraFileExtensions: ['.vue'],
  },
  rules: {
    'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    'no-debugger': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
    '@typescript-eslint/no-unused-vars': [
      'warn',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
    ],
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
  overrides: [
    {
      // 测试代码与测试工具：允许 mock 场景下的非空断言与调试输出
      files: [
        'src/**/__tests__/**/*.{ts,tsx}',
        'src/**/*.{spec,test}.{ts,tsx}',
        'src/test-utils/**/*.ts',
        'vitest.setup.ts',
      ],
      rules: {
        '@typescript-eslint/no-non-null-assertion': 'off',
        'no-console': 'off',
      },
    },
    {
      // 命令行脚本使用 Node 环境
      files: ['scripts/**/*.{js,mjs,cjs}'],
      env: { node: true, es2022: true },
      rules: {
        'no-console': 'off',
      },
    },
  ],
}
