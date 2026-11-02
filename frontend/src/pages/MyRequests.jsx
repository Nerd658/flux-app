import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.js";
import RequestList from "../components/RequestList.jsx";
import { STATUS_GROUPS as GROUPS } from "../components/StatusBadge.jsx";
import { ErrorBanner, PageHero } from "../components/ui.jsx";
import { IconPlus, IconSearch } from "../components/icons.jsx";

export default function MyRequests() {
  const { user } = useAuth();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [group, setGroup] = useState("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.mine().then(setRows).catch((e) => setError(e.message));
  }, []);

  const counts = useMemo(
    () => Object.fromEntries(GROUPS.map((g) => [g.key, rows ? rows.filter((r) => g.match(r.statut)).length : 0])),
    [rows],
  );

  const filtered = useMemo(() => {
    if (!rows) return null;
    const g = GROUPS.find((x) => x.key === group);
    const q = query.trim().toLowerCase();
    return rows.filter((r) => g.match(r.statut) && (!q || `${r.reference} ${r.flux_type}`.toLowerCase().includes(q)));
  }, [rows, group, query]);

  const greetingName = user.prenom && user.prenom !== "-" ? user.prenom : (user.nom && user.nom !== "-" && user.nom !== user.cuid ? user.nom : user.cuid);

  return (
    <div>
      <PageHero kicker="Espace demandeur" title={`Bonjour ${greetingName}`}
                lead="Voici l'avancement de vos demandes d'ouverture de flux."
                actions={<Link className="btn btn-primary" to="/nouvelle-demande"><IconPlus width={18} height={18} />Nouvelle demande</Link>} />

      <ErrorBanner title="Chargement impossible" message={error} />

      {/* Compteurs servant aussi de filtres */}
      <div className="stats-grid filters" role="tablist" aria-label="Filtrer par statut">
        {GROUPS.map((g) => (
          <button key={g.key} role="tab" aria-selected={group === g.key}
                  className={`stat-box ${group === g.key ? "on" : ""}`} data-tone={g.key} onClick={() => setGroup(g.key)}>
            <span className="stat-label">{g.label}</span>
            <strong className="num">{counts[g.key]}</strong>
            <span className="stat-meta">{g.meta}</span>
          </button>
        ))}
      </div>

      <section className="table-card">
        <div className="table-card-heading">
          <div>
            <h2>Historique</h2>
            <p>Cliquez sur une demande pour voir son détail, son circuit de validation et son PDF.</p>
          </div>
          <label className="search">
            <IconSearch width={18} height={18} />
            <input className="text-input" type="search" placeholder="Rechercher une référence ou un type" value={query}
                   onChange={(e) => setQuery(e.target.value)} aria-label="Rechercher une demande" />
          </label>
        </div>
        <RequestList
          rows={filtered}
          empty={rows?.length ? "Aucune demande ne correspond à ce filtre." : "Aucune demande pour l'instant."}
          emptyHint={!rows?.length ? "Votre première demande apparaîtra ici dès son envoi." : undefined}
          emptyAction={!rows?.length && <Link className="btn btn-primary" to="/nouvelle-demande">Faire une demande</Link>}
        />
      </section>
    </div>
  );
}
