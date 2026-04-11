import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'

function normalizeDetail(detail) {
  if (detail === null || detail === undefined) return ''
  if (typeof detail === 'string') return detail
  if (typeof detail === 'number' || typeof detail === 'boolean') return String(detail)

  if (Array.isArray(detail)) {
    return detail.map((item) => normalizeDetail(item)).filter(Boolean).join('\n')
  }

  if (typeof detail === 'object') {
    if (typeof detail.detail === 'string') return detail.detail
    if (typeof detail.message === 'string') return detail.message
    if (typeof detail.msg === 'string') return detail.msg

    return Object.entries(detail)
      .map(([key, value]) => {
        const normalizedValue = normalizeDetail(value)
        return normalizedValue ? `${key}: ${normalizedValue}` : ''
      })
      .filter(Boolean)
      .join('\n')
  }

  return ''
}

export function getErrorMessage(error, fallback = 'Что-то пошло не так') {
  const detail =
    error?.response?.data?.detail ??
    error?.response?.data?.message ??
    error?.message

  const normalized = normalizeDetail(detail).trim()
  return normalized || fallback
}

export function useUi() {
  const toast = useToast()
  const confirm = useConfirm()

  const notify = ({
    severity = 'info',
    summary = 'Информация',
    detail,
    life = 3500,
  }) => {
    toast.add({
      group: 'app',
      severity,
      summary,
      detail,
      life,
    })
  }

  const confirmAction = ({
    header = 'Подтвердите действие',
    message,
    icon = 'pi pi-exclamation-triangle',
    acceptLabel = 'Подтвердить',
    rejectLabel = 'Отмена',
    acceptSeverity = 'primary',
  }) =>
    new Promise((resolve) => {
      let settled = false
      const done = (result) => {
        if (settled) return
        settled = true
        resolve(result)
      }

      confirm.require({
        group: 'app-confirm',
        header,
        message,
        icon,
        rejectProps: {
          label: rejectLabel,
          severity: 'secondary',
          outlined: true,
        },
        acceptProps: {
          label: acceptLabel,
          severity: acceptSeverity,
        },
        accept: () => done(true),
        reject: () => done(false),
        onHide: () => done(false),
      })
    })

  return {
    success(detail, summary = 'Готово', life = 3000) {
      notify({ severity: 'success', summary, detail, life })
    },
    info(detail, summary = 'Информация', life = 3000) {
      notify({ severity: 'info', summary, detail, life })
    },
    warn(detail, summary = 'Внимание', life = 3500) {
      notify({ severity: 'warn', summary, detail, life })
    },
    error(detail, summary = 'Ошибка', life = 4500) {
      notify({ severity: 'error', summary, detail, life })
    },
    confirm: confirmAction,
    getErrorMessage,
  }
}
