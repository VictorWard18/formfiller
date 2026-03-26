import React, { useState, useEffect, useRef, useCallback } from 'react'
import translations from './i18n'

const API = '/api'

// ─── Helpers ────────────────────────────────────────────────
function flattenDict(obj, prefix = '') {
  const result = []
  for (const [key, val] of Object.entries(obj || {})) {
    const fullKey = prefix ? `${prefix}.${key}` : key
    if (val === null || val === undefined) continue
    if (Array.isArray(val)) {
      val.forEach((item, i) => {
        if (typeof item === 'object') {
          result.push(...flattenDict(item, `${fullKey}[${i}]`))
        } else {
          result.push({ key: `${fullKey}[${i}]`, value: String(item) })
        }
      })
    } else if (typeof val === 'object') {
      result.push(...flattenDict(val, fullKey))
    } else {
      result.push({ key: fullKey, value: String(val) })
    }
  }
  return result
}

function unflattenDict(flatEntries) {
  const root = {}
  for (const { key, value } of flatEntries) {
    const parts = key.replace(/\[(\d+)\]/g, '.$1').split('.')
    let current = root
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts[i]
      const next = parts[i + 1]
      if (!current[p]) {
        current[p] = /^\d+$/.test(next) ? [] : {}
      }
      current = current[p]
    }
    const last = parts[parts.length - 1]
    current[last] = value
  }
  return root
}

// ─── Styles ─────────────────────────────────────────────────
const css = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'IBM Plex Sans', -apple-system, sans-serif;
    background: #f7f6f3;
    color: #1a1a1a;
    line-height: 1.5;
  }
  .container { max-width: 740px; margin: 0 auto; padding: 2rem 1.5rem; }
  .header {
    display: flex; align-items: center; gap: 14px;
    margin-bottom: 2rem; flex-wrap: wrap;
  }
  .logo {
    width: 40px; height: 40px; border-radius: 10px;
    background: #1a1a1a; display: flex; align-items: center;
    justify-content: center; color: #fff; font-weight: 600;
    font-size: 16px; flex-shrink: 0;
  }
  .header-text h1 { font-size: 20px; font-weight: 600; }
  .header-text p { font-size: 13px; color: #888; }
  .lang-toggle {
    margin-left: auto; display: flex; gap: 0;
    background: #eee; border-radius: 8px; overflow: hidden;
  }
  .lang-btn {
    padding: 6px 14px; font-size: 12px; font-weight: 500;
    border: none; cursor: pointer; background: transparent;
    color: #666; transition: all 0.15s;
  }
  .lang-btn.active {
    background: #1a1a1a; color: #fff;
  }

  .steps {
    display: flex; gap: 6px; margin-bottom: 1.5rem;
  }
  .step {
    flex: 1; display: flex; align-items: center; gap: 8px;
    padding: 10px 14px; border-radius: 10px;
    background: #eee; cursor: pointer; transition: all 0.15s;
  }
  .step.active { background: #1a1a1a; color: #fff; }
  .step.done { background: #e8f5e9; color: #2e7d32; }
  .step-num {
    width: 22px; height: 22px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 12px; font-weight: 600; flex-shrink: 0;
    background: rgba(0,0,0,0.08);
  }
  .step.active .step-num { background: rgba(255,255,255,0.2); }
  .step.done .step-num { background: #2e7d32; color: #fff; }
  .step-label { font-size: 13px; font-weight: 500; }

  .card {
    background: #fff; border: 1px solid #e8e6e1;
    border-radius: 14px; padding: 1.5rem; margin-bottom: 1rem;
  }
  .card-title {
    font-size: 14px; font-weight: 600; margin-bottom: 14px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .card-title .badge {
    font-size: 12px; font-weight: 400; color: #888;
  }

  .dropzone {
    border: 2px dashed #d0cec8; border-radius: 10px;
    padding: 2rem; text-align: center; cursor: pointer;
    transition: all 0.15s;
  }
  .dropzone:hover, .dropzone.dragover {
    border-color: #1a1a1a; background: #faf9f7;
  }
  .dropzone p { font-size: 13px; color: #888; }
  .dropzone p.hint { font-size: 12px; color: #aaa; margin-top: 4px; }

  .file-list { margin-top: 12px; display: flex; flex-direction: column; gap: 4px; }
  .file-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; background: #f7f6f3; border-radius: 8px;
    font-size: 13px;
  }
  .file-item .status { margin-left: auto; font-size: 12px; }
  .file-item .status.ok { color: #2e7d32; }
  .file-item .status.pending { color: #e65100; }
  .file-item .status.error { color: #c62828; }
  .file-item .remove {
    background: none; border: none; cursor: pointer;
    color: #aaa; font-size: 16px; padding: 0 4px;
  }

  .btn {
    width: 100%; padding: 12px; font-size: 14px; font-weight: 500;
    border: none; border-radius: 10px; cursor: pointer;
    transition: all 0.15s; margin-top: 14px; font-family: inherit;
  }
  .btn-primary { background: #1a1a1a; color: #fff; }
  .btn-primary:hover { background: #333; }
  .btn-primary:disabled { background: #ccc; cursor: not-allowed; }
  .btn-secondary {
    background: transparent; color: #1a1a1a;
    border: 1px solid #d0cec8;
  }
  .btn-secondary:hover { background: #f7f6f3; }
  .btn-danger { background: #fff0f0; color: #c62828; border: 1px solid #ffcdd2; }
  .btn-sm { width: auto; padding: 6px 16px; font-size: 13px; margin-top: 0; }

  .dict-table {
    border: 1px solid #e8e6e1; border-radius: 10px;
    overflow: hidden; font-size: 13px;
  }
  .dict-row {
    display: flex; align-items: stretch;
    border-bottom: 1px solid #f0eeea;
  }
  .dict-row:last-child { border-bottom: none; }
  .dict-row:nth-child(odd) { background: #faf9f7; }
  .dict-key {
    width: 40%; padding: 8px 12px; color: #666;
    font-family: 'JetBrains Mono', monospace; font-size: 11px;
    word-break: break-all; display: flex; align-items: center;
  }
  .dict-val {
    flex: 1; padding: 8px 12px; display: flex;
    align-items: center; gap: 8px;
  }
  .dict-val input {
    width: 100%; border: none; background: transparent;
    font-size: 13px; font-family: inherit; outline: none;
    padding: 2px 0;
  }
  .dict-val input:focus {
    background: #fff8e1; border-radius: 4px; padding: 2px 6px;
  }

  .input-field {
    width: 100%; padding: 10px 14px; border: 1px solid #d0cec8;
    border-radius: 10px; font-size: 14px; font-family: inherit;
    outline: none; background: #fff;
  }
  .input-field:focus { border-color: #1a1a1a; }

  .existing-list { margin-bottom: 1rem; }
  .existing-item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; background: #f7f6f3; border-radius: 10px;
    margin-bottom: 6px;
  }
  .existing-item .info { flex: 1; }
  .existing-item .info .name { font-size: 14px; font-weight: 500; }
  .existing-item .info .meta { font-size: 12px; color: #888; }

  .message {
    padding: 12px 16px; border-radius: 10px;
    font-size: 13px; margin-bottom: 1rem;
  }
  .message.success { background: #e8f5e9; color: #2e7d32; }
  .message.error { background: #fff0f0; color: #c62828; }
  .message.info { background: #e3f2fd; color: #1565c0; }

  .login-wrapper {
    min-height: 100vh; display: flex; align-items: center;
    justify-content: center;
  }
  .login-card {
    background: #fff; border: 1px solid #e8e6e1;
    border-radius: 14px; padding: 2rem; width: 340px;
    text-align: center;
  }
  .login-card h2 { font-size: 18px; margin-bottom: 1rem; }
  .login-card .input-field { margin-bottom: 1rem; }

  .spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff; border-radius: 50%;
    animation: spin 0.6s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .select-field {
    width: 100%; padding: 10px 14px; border: 1px solid #d0cec8;
    border-radius: 10px; font-size: 14px; font-family: inherit;
    outline: none; background: #fff; appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%23888' stroke-width='1.5' fill='none'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 14px center;
  }
`

// ─── Main App ───────────────────────────────────────────────
export default function App() {
  const [lang, setLang] = useState('ru')
  const [authed, setAuthed] = useState(false)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [step, setStep] = useState(1)

  // Step 1
  const [pdfFiles, setPdfFiles] = useState([])
  const [dictName, setDictName] = useState('')
  const [extracting, setExtracting] = useState(false)

  // Step 2
  const [dictionaries, setDictionaries] = useState([])
  const [activeDict, setActiveDict] = useState(null)
  const [flatFields, setFlatFields] = useState([])
  const [saveStatus, setSaveStatus] = useState(null)

  // Step 3
  const [formFiles, setFormFiles] = useState([])
  const [filling, setFilling] = useState(false)
  const [fillMessage, setFillMessage] = useState(null)

  const [error, setError] = useState(null)

  const t = translations[lang]

  // Check if auth is needed
  useEffect(() => {
    fetch(`${API}/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: '' }),
    })
      .then((r) => { if (r.ok) setAuthed(true); setCheckingAuth(false) })
      .catch(() => setCheckingAuth(false))
  }, [])

  // Load dictionaries
  const loadDicts = useCallback(() => {
    fetch(`${API}/dictionaries`)
      .then((r) => r.json())
      .then(setDictionaries)
      .catch(() => {})
  }, [])

  useEffect(() => { if (authed) loadDicts() }, [authed, loadDicts])

  // When activeDict changes, flatten for editor
  useEffect(() => {
    if (activeDict?.data) {
      setFlatFields(flattenDict(activeDict.data))
    }
  }, [activeDict])

  // ─── Auth ───
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState(false)

  const handleLogin = () => {
    fetch(`${API}/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    }).then((r) => {
      if (r.ok) { setAuthed(true); setAuthError(false) }
      else setAuthError(true)
    })
  }

  // ─── Step 1: Extract ───
  const handleExtract = async () => {
    if (pdfFiles.length === 0) return
    setExtracting(true)
    setError(null)

    const formData = new FormData()
    pdfFiles.forEach((f) => formData.append('files', f))
    formData.append('language', lang)
    formData.append('name', dictName || 'New Dictionary')

    try {
      const res = await fetch(`${API}/extract`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Extraction failed')
      }
      const data = await res.json()
      setActiveDict(data)
      loadDicts()
      setStep(2)
      setPdfFiles([])
    } catch (e) {
      setError(e.message)
    } finally {
      setExtracting(false)
    }
  }

  // ─── Step 2: Save edits ───
  const handleFieldChange = (index, newValue) => {
    const updated = [...flatFields]
    updated[index] = { ...updated[index], value: newValue }
    setFlatFields(updated)
    setSaveStatus(null)
  }

  const handleSaveDict = async () => {
    if (!activeDict?.id) return
    const reconstructed = unflattenDict(flatFields)
    try {
      const res = await fetch(`${API}/dictionaries/${activeDict.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: reconstructed }),
      })
      if (res.ok) {
        setSaveStatus('ok')
        setActiveDict({ ...activeDict, data: reconstructed })
        setTimeout(() => setSaveStatus(null), 2000)
      }
    } catch (e) {
      setError(e.message)
    }
  }

  // ─── Step 3: Fill forms ───
  const handleFill = async () => {
    if (formFiles.length === 0 || !activeDict?.id) return
    setFilling(true)
    setFillMessage(null)
    setError(null)

    const formData = new FormData()
    formFiles.forEach((f) => formData.append('files', f))
    formData.append('dictionary_id', activeDict.id)
    formData.append('language', lang)

    try {
      const res = await fetch(`${API}/fill`, { method: 'POST', body: formData })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Fill failed')
      }

      // Trigger download
      const blob = await res.blob()
      const contentDisp = res.headers.get('Content-Disposition') || ''
      const match = contentDisp.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : 'filled_forms.zip'

      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)

      setFillMessage('success')
      setFormFiles([])
    } catch (e) {
      setError(e.message)
    } finally {
      setFilling(false)
    }
  }

  // ─── Drag & Drop ───
  const makeDrop = (accept, setter) => {
    const [dragOver, setDragOver] = useState(false)
    const inputRef = useRef(null)

    const onDrop = (e) => {
      e.preventDefault()
      setDragOver(false)
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        accept.some((ext) => f.name.toLowerCase().endsWith(ext))
      )
      setter((prev) => [...prev, ...files])
    }

    return {
      dragOver,
      inputRef,
      dropProps: {
        className: `dropzone${dragOver ? ' dragover' : ''}`,
        onDragOver: (e) => { e.preventDefault(); setDragOver(true) },
        onDragLeave: () => setDragOver(false),
        onDrop,
        onClick: () => inputRef.current?.click(),
      },
      inputProps: {
        ref: inputRef,
        type: 'file',
        multiple: true,
        accept: accept.join(','),
        style: { display: 'none' },
        onChange: (e) => {
          setter((prev) => [...prev, ...Array.from(e.target.files)])
          e.target.value = ''
        },
      },
    }
  }

  const pdfDrop = makeDrop(['.pdf'], setPdfFiles)
  const docxDrop = makeDrop(['.docx', '.doc'], setFormFiles)

  // ─── Render ───
  if (checkingAuth) return null

  if (!authed) {
    return (
      <>
        <style>{css}</style>
        <div className="login-wrapper">
          <div className="login-card">
            <div className="logo" style={{ margin: '0 auto 1rem' }}>FF</div>
            <h2>{t.loginTitle}</h2>
            {authError && <div className="message error">{t.wrongPassword}</div>}
            <input
              className="input-field"
              type="password"
              placeholder={t.password}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            />
            <button className="btn btn-primary" onClick={handleLogin}>{t.login}</button>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <style>{css}</style>
      <div className="container">
        {/* Header */}
        <div className="header">
          <div className="logo">FF</div>
          <div className="header-text">
            <h1>{t.appName}</h1>
            <p>{t.appDesc}</p>
          </div>
          <div className="lang-toggle">
            <button className={`lang-btn${lang === 'ru' ? ' active' : ''}`} onClick={() => setLang('ru')}>RU</button>
            <button className={`lang-btn${lang === 'en' ? ' active' : ''}`} onClick={() => setLang('en')}>EN</button>
          </div>
        </div>

        {/* Steps */}
        <div className="steps">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`step${step === s ? ' active' : ''}${step > s ? ' done' : ''}`}
              onClick={() => {
                if (s <= 2 || activeDict) setStep(s)
              }}
            >
              <div className="step-num">{step > s ? '✓' : s}</div>
              <span className="step-label">{t[`step${s}`]}</span>
            </div>
          ))}
        </div>

        {error && <div className="message error">{error}</div>}

        {/* ─── Step 1: Upload PDFs ─── */}
        {step === 1 && (
          <>
            {/* Existing dictionaries */}
            {dictionaries.length > 0 && (
              <div className="card">
                <div className="card-title">{t.existingDicts}</div>
                <div className="existing-list">
                  {dictionaries.map((d) => (
                    <div key={d.id} className="existing-item">
                      <div className="info">
                        <div className="name">{d.name}</div>
                        <div className="meta">{t.created}: {new Date(d.created_at).toLocaleDateString()} · {d.language.toUpperCase()}</div>
                      </div>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={async () => {
                          const res = await fetch(`${API}/dictionaries/${d.id}`)
                          const full = await res.json()
                          setActiveDict(full)
                          setStep(2)
                        }}
                      >{t.useThis}</button>
                    </div>
                  ))}
                </div>
                <div style={{ textAlign: 'center', color: '#888', fontSize: 13, margin: '8px 0' }}>
                  — {t.orCreateNew} —
                </div>
              </div>
            )}

            <div className="card">
              <div className="card-title">{t.uploadPdfs}</div>
              <div {...pdfDrop.dropProps}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="1.5" style={{ margin: '0 auto 8px', display: 'block' }}>
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <p>{t.uploadPdfsHint}</p>
                <p className="hint">{t.uploadPdfsSubhint}</p>
                <input {...pdfDrop.inputProps} />
              </div>

              {pdfFiles.length > 0 && (
                <div className="file-list">
                  {pdfFiles.map((f, i) => (
                    <div key={i} className="file-item">
                      <span>📄</span>
                      <span>{f.name}</span>
                      <span className="status ok">{(f.size / 1024).toFixed(0)} KB</span>
                      <button className="remove" onClick={() => setPdfFiles((prev) => prev.filter((_, j) => j !== i))}>×</button>
                    </div>
                  ))}
                </div>
              )}

              <input
                className="input-field"
                style={{ marginTop: 14 }}
                placeholder={t.dictNamePlaceholder}
                value={dictName}
                onChange={(e) => setDictName(e.target.value)}
              />

              <button
                className="btn btn-primary"
                disabled={pdfFiles.length === 0 || extracting}
                onClick={handleExtract}
              >
                {extracting && <span className="spinner" />}
                {extracting ? t.building : t.buildDict}
              </button>
            </div>
          </>
        )}

        {/* ─── Step 2: Dictionary Editor ─── */}
        {step === 2 && activeDict && (
          <div className="card">
            <div className="card-title">
              {t.dictTitle}: {activeDict.name}
              <span className="badge">{flatFields.length} {t.fieldsExtracted}</span>
            </div>

            <div className="dict-table">
              {flatFields.map((f, i) => (
                <div key={f.key} className="dict-row">
                  <div className="dict-key">{f.key}</div>
                  <div className="dict-val">
                    <input
                      value={f.value}
                      onChange={(e) => handleFieldChange(i, e.target.value)}
                    />
                  </div>
                </div>
              ))}
            </div>

            <p style={{ fontSize: 12, color: '#888', textAlign: 'center', marginTop: 8 }}>
              {t.editHint}
            </p>

            <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
              <button className="btn btn-secondary" style={{ flex: 1 }} onClick={() => setStep(1)}>
                {t.back}
              </button>
              <button className="btn btn-primary" style={{ flex: 1, marginTop: 0 }} onClick={handleSaveDict}>
                {saveStatus === 'ok' ? `✓ ${t.saved}` : t.saveChanges}
              </button>
              <button className="btn btn-primary" style={{ flex: 1, marginTop: 0 }} onClick={() => setStep(3)}>
                {t.step3} →
              </button>
            </div>
          </div>
        )}

        {/* ─── Step 3: Fill Forms ─── */}
        {step === 3 && (
          <div className="card">
            {!activeDict ? (
              <div className="message info">{t.noDict}</div>
            ) : (
              <>
                <div className="card-title">
                  {t.uploadForms}
                  <span className="badge">{t.selectDict}: {activeDict.name}</span>
                </div>

                <div {...docxDrop.dropProps}>
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#aaa" strokeWidth="1.5" style={{ margin: '0 auto 8px', display: 'block' }}>
                    <rect x="2" y="3" width="20" height="18" rx="2" /><path d="M8 7h8M8 11h8M8 15h4" />
                  </svg>
                  <p>{t.uploadFormsHint}</p>
                  <input {...docxDrop.inputProps} />
                </div>

                {formFiles.length > 0 && (
                  <div className="file-list">
                    {formFiles.map((f, i) => (
                      <div key={i} className="file-item">
                        <span>📝</span>
                        <span>{f.name}</span>
                        <span className="status ok">{(f.size / 1024).toFixed(0)} KB</span>
                        <button className="remove" onClick={() => setFormFiles((prev) => prev.filter((_, j) => j !== i))}>×</button>
                      </div>
                    ))}
                  </div>
                )}

                {fillMessage === 'success' && (
                  <div className="message success">{t.downloadReady}</div>
                )}

                <button
                  className="btn btn-primary"
                  disabled={formFiles.length === 0 || filling}
                  onClick={handleFill}
                >
                  {filling && <span className="spinner" />}
                  {filling ? t.filling : t.fillForms}
                </button>

                <button className="btn btn-secondary" onClick={() => setStep(2)}>
                  ← {t.step2}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </>
  )
}
