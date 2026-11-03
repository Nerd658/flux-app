import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.js";
import RequestView from "../components/RequestView.jsx";
import StatusBadge, { STATUS } from "../components/StatusBadge.jsx";
import { ErrorBanner, Loading, Modal, Notice, PageHero, formatDateTime, useToast } from "../components/ui.jsx";
import {
  IconAlert, IconArrowLeft, IconCheck, IconDownload, IconFingerprint, IconShield, IconX,
} from "../components/icons.jsx";

// Statut attendu pour que chaque rôle de validateur puisse statuer
const ACTIONABLE = {
  manager: "soumise",
  securite: "validee_manager",
  rssi: "validee_technique",
};
// Retour vers la liste propre à chaque rôle
const BACK = {
  demandeur: ["/mes-demandes", "Mes demandes"],
  admin: ["/admin/demandes", "Toutes les demandes"],
};

// Circuit de validation : soumission, Manager, Technique, RSSI
function Tracker({ req }) {
  const s = STATUS[req.statut] || { tone: "wait", step: 0 };
  const v = (n) => req.validations.find((x) => x.niveau === n);
  const step = (n) => {
    const val = v(n);
    if (val) return { state: val.decision === "validee" ? "done" : "ko", who: val.validateur, when: val.decided_at, decision: val.decision };
    if (s.tone === "wait" && s.step === n - 1) return { state: "current" };
    return { state: "todo" };
  };
  const items = [
    { title: "Soumise", state: "done", who: `${req.demandeur.prenom} ${req.demandeur.nom.toUpperCase()}`, when: req.created_at },
    { title: "Manager de département", ...step(1) },
    { title: "Validateur Technique", ...step(2) },
    { title: "RSSI", ...step(3) },
  ];
  return (
    <ol className="tracker">
      {items.map((it) => (
        <li key={it.title} className={it.state}>
          <span className="tracker-dot">
            {it.state === "done" ? <IconCheck width={14} height={14} /> : it.state === "ko" ? <IconX width={14} height={14} /> : null}
          </span>
          <div>
            <strong>{it.title}</strong>
            <span className="field-hint">
              {it.state === "current" ? "En attente de décision"
                : it.state === "todo" ? "À venir"
                : `${it.decision === "refusee" ? "Refusée par" : it.title === "Soumise" ? "Par" : "Validée par"} ${it.who}, le ${formatDateTime(it.when)}`}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}

function SealPanel({ req, check, onVerify }) {
  const levelLabels = { 1: "Manager", 2: "Technique", 3: "RSSI" };
  return (
    <section className="card seal">
      <h3><IconFingerprint width={18} height={18} />Sceau d'intégrité</h3>
      <p className="field-hint">Le contenu est haché dès l'envoi ; chaque décision est signée par la clé de son validateur.</p>
      <dl className="seal-list">
        <div><dt>Empreinte du contenu</dt><dd className="num hash" title={req.content_hash}>{req.content_hash.slice(0, 16)}…</dd></div>
        {req.validations.map((v) => (
          <div key={v.niveau}><dt>Signature {levelLabels[v.niveau] || `Niveau ${v.niveau}`}</dt><dd className="num hash" title={v.key_fingerprint}>{v.key_fingerprint.slice(0, 16)}…</dd></div>
        ))}
      </dl>
      <button className="btn btn-secondary block" onClick={onVerify}><IconShield width={18} height={18} />Vérifier l'intégrité</button>
      {check && (
        <p className={`seal-result ${check.document_fiable ? "ok" : "ko"}`} role="status">
          {check.document_fiable ? <IconCheck /> : <IconAlert />}
          {check.document_fiable
            ? `Document intègre, ${check.signatures.length} signature${check.signatures.length > 1 ? "s" : ""} valide${check.signatures.length > 1 ? "s" : ""}.`
            : "Sceau rompu : le document a été modifié après signature."}
        </p>
      )}
    </section>
  );
}

function DecisionPanel({ req, onDone }) {
  const toast = useToast();
  const [modal, setModal] = useState(null); // "validee" | "refusee"
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const close = useCallback(() => { setModal(null); setError(""); }, []);

  async function decide() {
    setBusy(true);
    setError("");
    try {
      await api.decide(req.id, modal, modal === "refusee" ? comment.trim() : null);
      toast(modal === "validee" ? `${req.reference} validée et signée` : `${req.reference} refusée`, modal === "validee" ? "success" : "info");
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card decision">
      <h3>Votre décision</h3>
      <p className="field-hint">Votre décision sera signée électroniquement et ne pourra plus être modifiée.</p>
      <div className="decision-actions">
        <button className="btn btn-success block" onClick={() => setModal("validee")}><IconCheck width={18} height={18} />Valider</button>
        <button className="btn btn-danger-outline block" onClick={() => setModal("refusee")}><IconX width={18} height={18} />Refuser</button>
      </div>

      {modal && (
        <Modal
          title={modal === "validee" ? `Valider ${req.reference} ?` : `Refuser ${req.reference}`}
          onClose={close}
          footer={
            <>
              <button className="btn btn-secondary" onClick={close} disabled={busy}>Annuler</button>
              {modal === "validee" ? (
                <button className="btn btn-success" onClick={decide} disabled={busy}>{busy ? "Signature…" : "Valider et signer"}</button>
              ) : (
                <button className="btn btn-danger" onClick={decide} disabled={busy || comment.trim().length < 5}>{busy ? "Envoi…" : "Refuser la demande"}</button>
              )}
            </>
          }
        >
          {modal === "validee" ? (
            <p>Votre nom, la mention « Validé » et la date seront apposés sur le document, avec votre signature électronique.</p>
          ) : (
            <label className="field">
              <span className="field-label">Motif du refus</span>
              <textarea className="text-input" rows={4} maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)}
                        placeholder="Saisir le motif du refus" />
              <span className="field-hint">Visible par le demandeur. 5 caractères minimum.</span>
            </label>
          )}
          <ErrorBanner title="Décision non enregistrée" message={error} />
        </Modal>
      )}
    </section>
  );
}

export default function RequestPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [req, setReq] = useState(null);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get(id).then(setReq).catch((e) => setError(e.message));
  }, [id]);

  const [back, backLabel] = BACK[user.role] || ["/validation", "Demandes à valider"];

  if (error && !req) {
    return (
      <div>
        <Link className="back-link" to={back}><IconArrowLeft width={16} height={16} />Retour</Link>
        <ErrorBanner title="Demande inaccessible" message={error} />
      </div>
    );
  }
  if (!req) return <Loading label="Chargement de la demande…" />;

  const refusal = req.validations.find((v) => v.decision === "refusee");
  const refusalRole = refusal ? ({ 1: "manager de département", 2: "validateur technique", 3: "RSSI" }[refusal.niveau] || "validateur") : "";
  const canDecide = ACTIONABLE[user.role] === req.statut &&
    (user.role !== "manager" || !req.manager_cuid || req.manager_cuid === user.cuid);

  async function verify() {
    try { setCheck(await api.verify(req.id)); } catch (e) { setError(e.message); }
  }
  async function pdf() {
    try {
      await api.downloadPdf(req.id, req.reference);
      toast("PDF téléchargé");
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <PageHero
        mono
        kicker={<Link className="hero-back" to={back}><IconArrowLeft width={15} height={15} />{backLabel}</Link>}
        title={req.reference}
        lead={
          <>
            <StatusBadge statut={req.statut} />
            {req.ticket_ref && (
              <span className="ticket-pill" title="Référence du ticket Oline (iTop)">
                Ticket Oline : {req.ticket_ref}
              </span>
            )}
            <span>Type {req.flux_type}, soumise le {formatDateTime(req.created_at)} par {req.demandeur.prenom} {req.demandeur.nom.toUpperCase()}</span>
          </>
        }
        actions={req.statut === "validee" && (
          <button className="btn btn-primary" onClick={pdf}><IconDownload width={18} height={18} />Télécharger le PDF</button>
        )}
      />

      <ErrorBanner message={error} title="Action impossible" />

      {refusal && (
        <Notice tone="error" className="refusal"
                title={`Refusée par ${refusal.validateur} (${refusalRole})`}>
          <p className="pre">{refusal.commentaire}</p>
          {user.role === "demandeur" && req.demandeur.email === user.email && (
            <Link className="btn btn-secondary btn-sm banner-action" to="/nouvelle-demande" state={{ from: req }}>
              Corriger et soumettre à nouveau
            </Link>
          )}
        </Notice>
      )}

      <div className="detail-grid">
        <div className="stack">
          <section className="card"><Tracker req={req} /></section>
          <section className="card"><RequestView req={req} /></section>
        </div>
        <aside className="stack side">
          {canDecide && <DecisionPanel req={req} onDone={() => navigate("/validation")} />}
          <SealPanel req={req} check={check} onVerify={verify} />
        </aside>
      </div>
    </div>
  );
}
