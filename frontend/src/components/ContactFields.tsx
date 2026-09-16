export function ContactFields({ values, onChange, prefix = '' }: { values: Record<string, string>; onChange: (field: string, value: string) => void; prefix?: string }) {
  return <>{[['first_name', 'Nome', 100], ['last_name', 'Cognome', 100], ['phone', 'Telefono', 32], ['email', 'Email', 255]].map(([key, label, max]) => {
    const field = `${prefix}${key}`
    return <label key={field}>{label}{key !== 'email' ? ' *' : ''}<input required={key !== 'email'} maxLength={Number(max)} type={key === 'email' ? 'email' : key === 'phone' ? 'tel' : 'text'} value={values[field] ?? ''} onChange={e => onChange(field, e.target.value)} /></label>
  })}</>
}
