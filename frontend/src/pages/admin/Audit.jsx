// Journal d'audit : lecture seule, filtres par catégorie et recherche, pagination « Charger plus »
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api.js";
import { ROLE_LABELS } from "../../auth.js";
import { ErrorBanner, formatDateTime, Loading, PageHero, useDebounced } from "../../components/ui.jsx";
import { IconSearch } from "../../components/icons.jsx";

const PAGE = 50;

const CATEGORIES = [
  { key: "", label: "Tout" },
  { key: "connexions", label: "Connexions" },
  { key: "demandes", label: "Demandes" },
  { key: "decisions", label: "Décisions" },
  { key: "administration", label: "Administration" },
];

// Mêmes préfixes que l'API (app/routers/admin.py) : sert à colorer chaque ligne
const PREFIXES = {
  connexions: ["LOGIN_", "LOGOUT"],
  demandes: ["REQUEST_SUBMITTED", "PDF_", "SEAL_"],
  decisions: ["REQUEST_VALIDEE", "REQUEST_REFUSEE", "SIGNING_KEY"],
  administration: ["USER_", "REFERENTIAL_", "FLUX_TYPE_", "DIRECTION_"],
};

const ACTIONS = {
  LOGIN_SUCCESS: "Connexion",
  LOGIN_FAILED: "Échec de connexion",
  LOGIN_BLOCKED: "Connexion bloquée (trop de tentatives)",
  LOGOUT: "Déconnexion",
  REQUEST_SUBMITTED: "Demande envoyée",
  PDF_DOWNLOADED: "PDF téléchargé",
  SEAL_BROKEN: "Sceau rompu détecté",
  REQUEST_VALIDEE_N1: "Validation N1",
  REQUEST_REFUSEE_N1: "Refus N1",
  REQUEST_VALIDEE_N2: "Validation finale",
  REQUEST_REFUSEE_N2: "Refus en validation finale",
  SIGNING_KEY_ISSUED: "Clé de signature émise",
  USER_CREATED: "Compte créé",
  USER_UPDATED: "Rôle modifié",
  USER_ACTIVATED: "Compte réactivé",
  USER_DEACTIVATED: "Compte désactivé",
  REFERENTIAL_CREATED: "Valeur de liste ajoutée",
  REFERENTIAL_UPDATED: "Valeur de liste renommée",
  REFERENTIAL_DELETED: "Valeur de liste supprimée",
  FLUX_TYPE_CREATED: "Type d'ouverture ajouté",
  DIRECTION_CREATED: "Direction ajoutée",
};

const ALERTS = new Set(["LOGIN_FAILED", "LOGIN_BLOCKED", "SEAL_BROKEN"]);

// Poste de connexion lisible à partir du navigateur transmis (ex. « Chrome 141 · Windows »)
const BROWSERS = [["Edg/", "Edge"], ["OPR/", "Opera"], ["Firefox/", "Firefox"], ["Chrome/", "Chrome"], ["Safari/", "Safari"]];
function device(ua) {
  if (!ua) return "—";
  const b = BROWSERS.find(([k]) => ua.includes(k));
  const version = b ? (ua.split(b[0])[1] || "").split(/[ .;)]/)[0] : "";
  const os = /Windows/.test(ua) ? "Windows" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return [b ? `${b[1]} ${version}`.trim() : "Navigateur non reconnu", os].filter(Boolean).join(" · ");
}
const FIELD_NAMES = { nom: "nom", prenom: "prénom", email: "email", telephone: "téléphone", departement: "direction", role: "rôle" };

const categoryOf = (action) => Object.entries(PREFIXES).find(([, ps]) => ps.some((p) => action.startsWith(p)))?.[0] || "";

function parse(details) {
  try {
    return details ? JSON.parse(details) : null;
  } catch {
    return null;
  }
}

// Détails lisibles : jamais de secret côté serveur, affichage en texte (aucun HTML interprété)
function Details({ row, d }) {
  const parts = [];
  if (row.entity === "flux_request" && row.entity_id) {
    parts.push(<Link key="req" className="ref" to={`/demandes/${row.entity_id}`}>{d.reference || `Demande n° ${row.entity_id}`}</Link>);
  }
  if (d.lignes) parts.push(<span key="l">{d.lignes} flux</span>);
  if (d.cuid && row.entity === "user") parts.push(<span key="c">CUID <b className="mono">{d.cuid}</b></span>);
  if (d.ancien_role) parts.push(<span key="o">{ROLE_LABELS[d.ancien_role] || d.ancien_role} →</span>);
  if (d.role) parts.push(<span key="r">rôle <b>{ROLE_LABELS[d.role] || d.role}</b></span>);
  if (d.mode === "secours") parts.push(<span key="m" className="tag-alert">Compte de secours</span>);
  if (d.mode === "annuaire") parts.push(<span key="m">via l'annuaire</span>);
  if (d.motif) parts.push(<span key="mo">{d.motif}</span>);
  if (Array.isArray(d.champs)) {
    parts.push(<span key="f">{d.champs.length ? `champs : ${d.champs.map((c) => FIELD_NAMES[c] || c).join(", ")}` : "aucun changement"}</span>);
  }
  if (d.libelle) parts.push(<span key="v">« {d.libelle} »</span>);
  if (d.ancien) parts.push(<span key="a">« {d.ancien} » → « {d.nouveau} »</span>);
  if (d.signed_hash) parts.push(<span key="h" className="mono" title={d.signed_hash}>empreinte {d.signed_hash.slice(0, 12)}…</span>);
  if (!parts.length) return <span className="muted">—</span>;
  return <span className="audit-details">{parts}</span>;
}

export default function AdminAudit() {
  const [category, setCategory] = useState("");
  const [query, setQuery] = useState("");
  const q = useDebounced(query.trim(), 350);
  const [rows, setRows] = useState(null);
  const [more, setMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true; // ignore les réponses d'un filtre déjà remplacé
    setRows(null);
    setError("");
    api.admin.audit({ categorie: category, q, limit: PAGE })
      .then((r) => { if (alive) { setRows(r); setMore(r.length === PAGE); } })
      .catch((e) => { if (alive) { setError(e.message); setRows([]); } });
    return () => { alive = false; };
  }, [category, q]);

  async function loadMore() {
    setLoadingMore(true);
    try {
      const r = await api.admin.audit({ categorie: category, q, limit: PAGE, before_id: rows[rows.length - 1].id });
      setRows((x) => [...x, ...r]);
      setMore(r.length === PAGE);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div>
      <PageHero kicker="Administration" title="Journal d'audit"
                lead="Les actions sensibles de la plateforme, horodatées et non modifiables. Aucun mot de passe n'y figure." />

      <ErrorBanner title="Chargement impossible" message={error} />

      <section className="table-card">
        <div className="toolbar">
          <div className="chips" role="tablist" aria-label="Catégorie">
            {CATEGORIES.map((c) => (
              <button key={c.key} type="button" role="tab" aria-selected={category === c.key}
                      className={`chip ${category === c.key ? "on" : ""}`} onClick={() => setCategory(c.key)}>
                {c.key && <i className={`cat-dot cat-${c.key}`} aria-hidden="true" />}{c.label}
              </button>
            ))}
          </div>
          <label className="search">
            <IconSearch width={18} height={18} />
            <input className="text-input" type="search" maxLength={50} placeholder="CUID, nom ou référence…"
                   value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Rechercher dans le journal" />
          </label>
        </div>

        {!rows ? <Loading label="Chargement du journal…" /> : rows.length === 0 ? (
          <div className="empty-state"><strong>Aucun événement ne correspond à ces critères.</strong></div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="data-table audit-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Action</th>
                    <th>CUID / auteur</th>
                    <th>Adresse IP</th>
                    <th>Poste</th>
                    <th>Détails</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const cat = categoryOf(r.action);
                    const d = parse(r.details) || {};
                    return (
                      <tr key={r.id}>
                        <td className="num nowrap">{formatDateTime(r.created_at)}</td>
                        <td>
                          <span className={`audit-action cat-${cat || "none"} ${ALERTS.has(r.action) ? "alert" : ""}`}>
                            {ACTIONS[r.action] || r.action}
                          </span>
                        </td>
                        <td>
                          {r.acteur ? (
                            <span className="actor"><b className="mono">{r.acteur_cuid}</b><small>{r.acteur}</small></span>
                          ) : d.cuid ? (
                            <span className="actor"><b className="mono">{d.cuid}</b><small>non authentifié</small></span>
                          ) : <span className="muted">—</span>}
                        </td>
                        <td className="mono nowrap">{r.ip || "—"}</td>
                        <td className="nowrap" title={d.poste || undefined}>{d.poste ? device(d.poste) : "—"}</td>
                        <td><Details row={r} d={d} /></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {more && (
              <div className="load-more">
                <button type="button" className="btn btn-secondary" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? "Chargement…" : "Charger plus"}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
