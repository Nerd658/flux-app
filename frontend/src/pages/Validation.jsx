// Validateurs : file « À traiter » + historique. Administrateur : toutes les demandes, en lecture seule.
import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { ROLE_LABELS, useAuth } from "../auth.js";
import RequestList from "../components/RequestList.jsx";
import { STATUS_GROUPS } from "../components/StatusBadge.jsx";
import { ErrorBanner, PageHero, Segmented } from "../components/ui.jsx";
import { IconCheck, IconClock, IconSearch, IconX } from "../components/icons.jsx";

export default function Validation() {
  const { user } = useAuth();
  const isAdmin = user.role === "admin";
  const [tab, setTab] = useState(isAdmin ? "all" : "pending");
  const [pending, setPending] = useState(null);
  const [all, setAll] = useState(null);
  const [group, setGroup] = useState("all");
  const [query, setQuery] = useState("");
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isAdmin) {
      api.pending().then(setPending).catch((e) => setError(e.message));
      api.validatorStats().then(setStats).catch((e) => setError(e.message));
    }
    api.all().then(setAll).catch((e) => setError(e.message));
  }, [isAdmin]);

  const source = tab === "pending" ? pending : all;
  const counts = useMemo(
    () => Object.fromEntries(STATUS_GROUPS.map((g) => [g.key, all ? all.filter((r) => g.match(r.statut)).length : 0])),
    [all],
  );
  const rows = useMemo(() => {
    if (!source) return null;
    const g = STATUS_GROUPS.find((x) => x.key === group);
    const q = query.trim().toLowerCase();
    return source.filter((r) => (tab === "pending" || g.match(r.statut))
      && (!q || `${r.reference} ${r.flux_type} ${r.demandeur}`.toLowerCase().includes(q)));
  }, [source, tab, group, query]);

  const level = user.role === "manager"
    ? "validation de manager de département"
    : user.role === "securite"
    ? "validation technique sécurité"
    : "validation finale RSSI";

  return (
    <div>
      <PageHero
        kicker={isAdmin ? "Pilotage" : ROLE_LABELS[user.role]}
        title={isAdmin ? "Toutes les demandes" : "Demandes à valider"}
        lead={isAdmin
          ? "Vue d'ensemble en lecture seule : l'administrateur consulte les demandes et leurs PDF, mais ne statue pas."
          : `Vous statuez sur les demandes en attente de ${level}, de la plus ancienne à la plus récente.`}
        actions={!isAdmin && (
          <Segmented label="Affichage" value={tab} onChange={setTab}
                     options={[
                       { value: "pending", label: `À traiter${pending ? ` (${pending.length})` : ""}` },
                       { value: "all", label: "Historique" },
                     ]} />
        )}
      />

      <ErrorBanner title="Chargement impossible" message={error} />

      {stats && (
        <div className="kpi-grid three">
          <div className={`kpi ${stats.en_retard ? "warn" : ""}`}>
            <div className="kpi-head"><span>À traiter</span><span className="kpi-icon"><IconClock /></span></div>
            <strong className="num">{stats.a_traiter}</strong>
            <small>{stats.en_retard ? `dont ${stats.en_retard} depuis plus de 48 h` : "aucune en retard"}</small>
          </div>
          <div className="kpi">
            <div className="kpi-head"><span>Validées par vous</span><span className="kpi-icon"><IconCheck /></span></div>
            <strong className="num">{stats.validees_mois}</strong>
            <small>depuis le début du mois</small>
          </div>
          <div className="kpi">
            <div className="kpi-head"><span>Refusées par vous</span><span className="kpi-icon"><IconX /></span></div>
            <strong className="num">{stats.refusees_mois}</strong>
            <small>depuis le début du mois</small>
          </div>
        </div>
      )}

      <section className="table-card">
        <div className="table-card-heading">
          <div>
            <h2>{tab === "pending" ? "À traiter" : "Historique des demandes"}</h2>
            <p>{tab === "pending" ? "Cliquez sur une demande pour l'examiner et statuer." : "Tous statuts confondus. Cliquez sur une demande pour l'ouvrir."}</p>
          </div>
        </div>
        <div className="toolbar">
          {tab === "all" ? (
            <div className="chips" role="tablist" aria-label="Filtrer par statut">
              {STATUS_GROUPS.map((g) => (
                <button key={g.key} type="button" role="tab" aria-selected={group === g.key}
                        className={`chip ${group === g.key ? "on" : ""}`} onClick={() => setGroup(g.key)}>
                  {g.label}<span className="num">{counts[g.key]}</span>
                </button>
              ))}
            </div>
          ) : <span />}
          <label className="search">
            <IconSearch width={18} height={18} />
            <input className="text-input" type="search" placeholder="Rechercher une demande" value={query}
                   onChange={(e) => setQuery(e.target.value)} aria-label="Rechercher une demande" />
          </label>
        </div>
        <RequestList
          rows={rows}
          showDemandeur
          empty={query || group !== "all" ? "Aucune demande ne correspond à ces critères." : tab === "pending" ? "Rien à traiter pour le moment." : "Aucune demande enregistrée."}
          emptyHint={tab === "pending" && !query ? "Les nouvelles demandes apparaîtront ici." : undefined}
        />
      </section>
    </div>
  );
}
