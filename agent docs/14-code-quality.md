# 14-code-quality.md

## Стандарты кода и тестирование

### Общая концепция

Единые стандарты качества кода для всего монорепозитория:

- TypeScript строгий режим
- ESLint + Prettier для фронтенда
- Black + isort + mypy для бэкенда
- Husky для pre-commit хуков
- Тестирование на всех уровнях

---

### Фронтенд стандарты

- Базовые UI-компоненты должны строиться на `shadcn/ui`.
- При разработке интерфейсов ориентироваться на визуальный подход студии Chulakov (типографика, сетка, иерархия, аккуратная визуальная система).

#### tsconfig.json (строгий режим)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "strictBindCallApply": true,
    "strictPropertyInitialization": true,
    "noImplicitThis": true,
    "useUnknownInCatchVariables": true,
    "alwaysStrict": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```
