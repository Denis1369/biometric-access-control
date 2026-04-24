export const ROLE_LABELS = Object.freeze({
  super_admin: 'Super Admin',
  checkpoint_operator: 'Оператор КПП',
})

export const ROLE_HOME_ROUTES = Object.freeze({
  super_admin: '/',
  checkpoint_operator: '/route',
})

export const ASSIGNABLE_ROLE_OPTIONS = Object.freeze([
  { value: 'super_admin', label: ROLE_LABELS.super_admin },
  { value: 'checkpoint_operator', label: ROLE_LABELS.checkpoint_operator },
])
