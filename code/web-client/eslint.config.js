import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
    {ignores: ['dist', 'node_modules']},
    eslint.configs.recommended,
    ...tseslint.configs.recommended,
    {
      files: ['**/*.{ts,tsx}'],
      rules: {
        '@typescript-eslint/consistent-type-imports': [
          'error',
          {prefer: 'type-imports', fixStyle: 'separate-type-imports'},
        ],
      },
    },
);
