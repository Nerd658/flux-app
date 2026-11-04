import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.js";
import FlowRoute from "../components/FlowRoute.jsx";
import {
  BrandMark, IconAlert, IconArrowLeft, IconCheck, IconFingerprint, IconSearch, IconShield, IconX,
} from "../components/icons.jsx";
import { formatDate, formatDateTime, Loading, Notice } from "../components/ui.jsx";

export default function Verify() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") || "");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function executeSearch(targetQuery) {
    const q = (targetQuery || query).trim();
    if (!q) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const data = await api.publicVerify(q);
      setResult(data);
      setParams({ q });
    } catch (err) {
      setError(err.message || "Aucune demande trouvée pour cette référence ou ce numéro de ticket.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const initial = params.get("q");
    if (initial) {
      setQuery(initial);
      executeSearch(initial);
    }
  }, []);

  function onSubmit(e) {
    e.preventDefault();
    executeSearch();
  }

  const isApproved = result && result.statut === "validee";
  const isReliable = result && result.document_fiable;

  return (
    <div className="verify-page">
      {!user && (
        <header className="verify-public-header">
          <div className="brand">
            <BrandMark />
            <span className="brand-text"><strong>Flux</strong><small>Orange Burkina · Sécurité SI</small></span>
          </div>
          <Link to="/connexion" className="btn btn-secondary btn-sm">
            <IconArrowLeft width={14} height={14} /> Retour à la connexion
          </Link>
        </header>
      )}

      <div className="verify-container">
        <div className="verify-hero">
          <div className="verify-badge">
            <IconShield width={20} height={20} />
            <span>Portail de vérification cryptographique</span>
          </div>
          <h1>Vérifier l'authenticité d'une ouverture de flux</h1>
          <p className="verify-lead">
            Contrôlez l'intégrité des règles réseau et la validité des signatures électroniques
            avant toute application sur les équipements pare-feu.
          </p>

          <form className="verify-search-bar" onSubmit={onSubmit}>
            <div className="verify-input-wrap">
              <IconSearch className="search-icon" width={18} height={18} />
              <input
                type="text"
                className="text-input verify-input"
                placeholder="Saisir la référence (ex. DOF-2026-000001) ou le ticket (ex. R-211299)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                autoFocus
              />
            </div>
            <button className="btn btn-primary" type="submit" disabled={busy || query.trim().length < 2}>
              {busy ? "Vérification…" : "Vérifier la demande"}
            </button>
          </form>
        </div>

        {busy && <Loading label="Vérification cryptographique en cours…" />}

        {error && (
          <div className="verify-empty-state">
            <Notice tone="error" title="Demande introuvable">
              {error}
            </Notice>
          </div>
        )}

        {result && (
          <div className="verify-result-stack">
            <div className={`verify-banner ${isReliable && isApproved ? "ok" : isApproved ? "ko" : "wait"}`}>
              <div className="banner-icon">
                {isReliable && isApproved ? <IconCheck width={28} height={28} /> : isApproved ? <IconAlert width={28} height={28} /> : <IconFingerprint width={28} height={28} />}
              </div>
              <div className="banner-text">
                <h2>
                  {isReliable && isApproved
                    ? "Document officiel certifié conforme et intègre"
                    : isApproved
                    ? "Alerte : Sceau d'intégrité rompu"
                    : `Demande en cours ou non finalisée (statut : ${result.statut})`}
                </h2>
                <p>
                  {isReliable && isApproved
                    ? "Les 3 signatures cryptographiques (Manager, Sécurité, RSSI) ont été authentifiées avec succès. Aucune règle n'a été modifiée après signature."
                    : isApproved
                    ? "Attention : Le contenu ou les signatures électroniques ont été altérés après la validation. L'ouverture de flux ne doit pas être exécutée."
                    : "Cette demande n'a pas encore atteint l'approbation finale du RSSI. Aucune règle ne doit être appliquée sur le pare-feu."}
                </p>
              </div>
            </div>

            <div className="card verify-summary-card">
              <h3>Informations de la demande</h3>
              <dl className="verify-facts-grid">
                <div>
                  <dt>Référence officielle</dt>
                  <dd className="num"><strong>{result.reference}</strong></dd>
                </div>
                <div>
                  <dt>Ticket d'exploitation Oline</dt>
                  <dd>
                    {result.ticket_ref ? (
                      <span className="ticket-pill">{result.ticket_ref}</span>
                    ) : (
                      <span className="field-hint">Aucun ticket généré</span>
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Demandeur</dt>
                  <dd><strong>{result.demandeur_nom}</strong></dd>
                </div>
                {result.direction && (
                  <div>
                    <dt>Direction</dt>
                    <dd>{result.direction}</dd>
                  </div>
                )}
                <div>
                  <dt>{result.direction ? "Département" : "Direction"}</dt>
                  <dd>{result.departement}</dd>
                </div>
                <div>
                  <dt>Type d'ouverture</dt>
                  <dd>{result.flux_type}</dd>
                </div>
                <div>
                  <dt>Période</dt>
                  <dd>
                    {result.periode === "temporaire"
                      ? `Du ${formatDate(result.date_debut)} au ${formatDate(result.date_fin)}`
                      : `Permanente (depuis le ${formatDate(result.date_debut)})`}
                  </dd>
                </div>
              </dl>
              <div className="verify-hash-box">
                <span className="person-title">Empreinte cryptographique du contenu (SHA-256)</span>
                <code className="num hash-display">{result.content_hash}</code>
              </div>
            </div>

            <div className="card">
              <h3>Chaîne d'approbation et signatures numériques (Ed25519)</h3>
              <div className="signatures-grid">
                {result.signatures.map((sig) => (
                  <div key={sig.niveau} className={`signature-card ${sig.signature_valide ? "valid" : "invalid"}`}>
                    <div className="sig-head">
                      <span className="sig-level">Niveau {sig.niveau}</span>
                      <span className={`sig-status ${sig.signature_valide ? "badge-ok" : "badge-ko"}`}>
                        {sig.signature_valide ? "Signature valide" : "Signature invalide"}
                      </span>
                    </div>
                    <strong>{sig.role_label}</strong>
                    <span className="sig-author">{sig.validateur_nom}</span>
                    <small className="field-hint">Signé le {formatDateTime(sig.decided_at)}</small>
                    <div className="sig-key">
                      <span>Empreinte de clé :</span>
                      <code className="num">{sig.key_fingerprint.slice(0, 16)}…</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-head">
                <h3>Règles de flux autorisées ({result.lines.length})</h3>
                <span className="field-hint">Règles conformes prêtes pour paramétrage pare-feu</span>
              </div>
              <ol className="flow-list">
                {result.lines.map((l) => (
                  <li key={l.numero} className="flow-item">
                    <span className="flow-num">{l.numero}</span>
                    <div className="flow-body">
                      <FlowRoute line={l} compact />
                      <dl className="flow-extra">
                        <div><dt>Type d'accès</dt><dd>{l.type_acces}</dd></div>
                        <div><dt>Pays</dt><dd>{l.src_pays} → {l.dst_pays}</dd></div>
                        <div className="wide"><dt>Justification</dt><dd>{l.justification}</dd></div>
                      </dl>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
