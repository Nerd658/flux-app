// Composants d'interface réutilisables (design system : styles.css)
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { IconAlert, IconCalendar, IconChevronLeft, IconChevronRight, IconInfo, IconX } from "./icons.jsx";

/* ---------------- Dates ---------------- */

const pad = (n) => String(n).padStart(2, "0");
export const toIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const todayIso = () => toIso(new Date());
const fromIso = (s) => {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
};
export const formatDateLong = (iso) =>
  iso ? fromIso(iso).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "long", year: "numeric" }) : "";
export const formatDate = (iso) => (iso ? fromIso(iso).toLocaleDateString("fr-FR") : "—");
export const daysBetween = (a, b) => Math.round((fromIso(b) - fromIso(a)) / 86400000) + 1;
// Les dates serveur sont en UTC ; MySQL les renvoie sans fuseau
const parseServer = (dt) => new Date(/[zZ]|[+-]\d\d:\d\d$/.test(dt) ? dt : `${dt}Z`);
export const formatDateTime = (dt) =>
  parseServer(dt).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

/* ---------------- Utilitaires ---------------- */

// Copie dans le presse-papiers ; repli pour les pages servies en HTTP sur l'intranet (API Clipboard indisponible)
export async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* repli ci-dessous */
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  area.remove();
  return ok;
}

export function useDebounced(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

/* ---------------- Bandeau de page (fond noir, cartes posées à cheval) ---------------- */

export function PageHero({ kicker, title, lead, actions, children, mono = false }) {
  return (
    <header className="hero">
      <div className="hero-row">
        <div className="hero-text">
          {kicker && <div className="kick">{kicker}</div>}
          <h1 className={mono ? "mono-title" : ""}>{title}</h1>
          {lead && <p className="lead">{lead}</p>}
        </div>
        {actions && <div className="hero-actions">{actions}</div>}
      </div>
      {children}
    </header>
  );
}

/* ---------------- Notifications ---------------- */

const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

let toastSeq = 0;
const uid = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${++toastSeq}-${Math.random().toString(36).slice(2, 7)}`;
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((message, tone = "success") => {
    const id = uid();
    setToasts((t) => [...t.slice(-2), { id, message, tone }]); // 3 messages au plus à l'écran
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.message}</div>)}
      </div>
    </ToastContext.Provider>
  );
}

/* ---------------- Fenêtre modale ---------------- */

export function Modal({ title, description, children, onClose, footer, size = "md" }) {
  const ref = useRef(null);
  const titleId = useId();
  useEffect(() => {
    const previous = document.activeElement;
    ref.current?.querySelector("textarea, input:not([type=hidden]), select, .modal-body button, .modal-foot button")?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.classList.add("modal-open");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("modal-open");
      previous?.focus?.(); // rend le focus à l'élément d'origine
    };
  }, [onClose]);
  // Portail vers <body> : la fenêtre couvre toujours l'écran, quel que soit le conteneur qui l'ouvre
  // (un parent avec backdrop-filter ou transform deviendrait sinon la référence du position: fixed)
  return createPortal(
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref}>
        <div className="modal-head">
          <div>
            <h2 id={titleId}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer"><IconX /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

// Confirmation d'une action sensible ; l'erreur éventuelle de l'API reste affichée dans la fenêtre
export function ConfirmDialog({ title, children, confirmLabel, tone = "primary", onConfirm, onClose }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run() {
    setBusy(true);
    setError("");
    try {
      await onConfirm();
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={busy}>Annuler</button>
          <button type="button" className={`btn btn-${tone}`} onClick={run} disabled={busy}>{busy ? "Patientez…" : confirmLabel}</button>
        </>
      }
    >
      {children}
      <ErrorBanner title="Action impossible" message={error} />
    </Modal>
  );
}

/* ---------------- Choix exclusif (contrôle segmenté) ---------------- */

export function Segmented({ value, options, onChange, label }) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value} type="button" role="radio" aria-checked={value === o.value}
          className={`choice-option ${value === o.value ? "on" : ""}`} onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Champ de formulaire ---------------- */

// group : conteneur <div> pour les contrôles composés (boutons), évite l'activation implicite d'un <label>
export function Field({ label, hint, error, children, className = "", group = false }) {
  const Tag = group ? "div" : "label";
  return (
    <Tag className={`field ${error ? "invalid" : ""} ${className}`} role={group ? "group" : undefined} aria-label={group ? label : undefined}>
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </Tag>
  );
}

/* ---------------- Calendrier (français, lundi en premier) ---------------- */

const WEEKDAYS = ["L", "M", "M", "J", "V", "S", "D"];

export function DatePicker({ value, onChange, min, placeholder = "Sélectionner une date", invalid, label }) {
  const [open, setOpen] = useState(false);
  const start = value ? fromIso(value) : min ? fromIso(min) : new Date();
  const [view, setView] = useState(new Date(start.getFullYear(), start.getMonth(), 1));
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const year = view.getFullYear();
  const month = view.getMonth();
  const offset = (new Date(year, month, 1).getDay() + 6) % 7; // lundi = 0
  const days = new Date(year, month + 1, 0).getDate();
  const cells = [...Array(offset).fill(null), ...Array.from({ length: days }, (_, i) => i + 1)];
  const today = todayIso();

  function toggle() {
    if (!open) {
      const s = value ? fromIso(value) : min ? fromIso(min) : new Date();
      setView(new Date(s.getFullYear(), s.getMonth(), 1));
    }
    setOpen(!open);
  }

  return (
    <div className="datepicker" ref={ref}>
      <button type="button" className={`text-input date-trigger ${invalid ? "invalid" : ""} ${value ? "" : "no-value"}`}
              onClick={toggle} aria-haspopup="dialog" aria-expanded={open} aria-label={label}>
        <IconCalendar />
        <span>{value ? formatDateLong(value) : placeholder}</span>
      </button>
      {open && (
        <div className="calendar" role="dialog" aria-label={label}>
          <div className="cal-head">
            <button type="button" className="icon-btn" aria-label="Mois précédent"
                    onClick={() => setView(new Date(year, month - 1, 1))}><IconChevronLeft /></button>
            <strong>{view.toLocaleDateString("fr-FR", { month: "long", year: "numeric" })}</strong>
            <button type="button" className="icon-btn" aria-label="Mois suivant"
                    onClick={() => setView(new Date(year, month + 1, 1))}><IconChevronRight /></button>
          </div>
          <div className="cal-grid">
            {WEEKDAYS.map((d, i) => <span key={i} className="cal-wd">{d}</span>)}
            {cells.map((d, i) => {
              if (!d) return <span key={i} />;
              const iso = toIso(new Date(year, month, d));
              const disabled = min && iso < min;
              return (
                <button
                  key={i} type="button" disabled={disabled}
                  className={`cal-day ${iso === value ? "sel" : ""} ${iso === today ? "today" : ""}`}
                  aria-label={formatDateLong(iso)} aria-pressed={iso === value}
                  onClick={() => { onChange(iso); setOpen(false); }}
                >
                  {d}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Messages ---------------- */

export function Notice({ tone = "", title, children, icon: Icon = tone === "error" ? IconAlert : IconInfo, className = "" }) {
  return (
    <div className={`notice ${tone} ${className}`} role={tone === "error" ? "alert" : undefined}>
      <Icon className="notice-icon" />
      <div className="notice-body">
        {title && <strong>{title}</strong>}
        {children}
      </div>
    </div>
  );
}

export function ErrorBanner({ message, title = "Certaines informations sont à corriger" }) {
  if (!message) return null;
  const lines = message.split("\n");
  return (
    <Notice tone="error" title={title}>
      {lines.length > 1 ? <ul>{lines.map((m, i) => <li key={i}>{m}</li>)}</ul> : <p>{message}</p>}
    </Notice>
  );
}

export function Loading({ label = "Chargement…" }) {
  return (
    <div className="empty-state loading" aria-busy="true">
      <span className="spinner" aria-hidden="true" />
      <strong>{label}</strong>
    </div>
  );
}

/* ---------------- Liste avec ajout (valeur partagée, stockée en base) ---------------- */

const ADD = "__add__";

export function SelectWithAdd({ value, options, onChange, onAdd, placeholder, addLabel, inputPlaceholder, invalid }) {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const ok = await onAdd(text.trim()); // le parent gère l'appel API et ses erreurs
      if (ok) { setAdding(false); setText(""); }
    } finally {
      setBusy(false);
    }
  }

  if (adding) {
    return (
      <div className="add-inline">
        <input className="text-input" autoFocus maxLength={40} placeholder={inputPlaceholder} value={text}
               onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (text.trim().length >= 2) submit(); } if (e.key === "Escape") setAdding(false); }} />
        <button type="button" className="btn btn-primary" disabled={busy || text.trim().length < 2} onClick={submit}>Ajouter</button>
        <button type="button" className="btn btn-secondary" onClick={() => { setAdding(false); setText(""); }}>Annuler</button>
      </div>
    );
  }
  return (
    <select className={`text-input select-input ${invalid ? "invalid" : ""} ${value ? "" : "is-empty"}`} value={value}
            onChange={(e) => (e.target.value === ADD ? setAdding(true) : onChange(e.target.value))}>
      <option value="" disabled>{placeholder}</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
      <option value={ADD}>{addLabel}</option>
    </select>
  );
}
