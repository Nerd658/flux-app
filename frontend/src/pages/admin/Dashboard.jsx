// Tableau de bord de l'administrateur : volumes, délais, retards et dernières demandes
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api.js";
import RequestList from "../../components/RequestList.jsx";
import { STATUS } from "../../components/StatusBadge.jsx";
import { ErrorBanner, Loading, PageHero } from "../../components/ui.jsx";
import { IconArrowRight, IconClock, IconFileCheck, IconGauge, IconInbox } from "../../components/icons.jsx";

const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

function formatDelay(hours) {
  if (hours == null) return "—";
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))} min`;
  if (hours < 48) return `${nf.format(hours)} h`;
  return `${nf.format(hours / 24)} j`;
}

function Kpi({ icon: Icon, label, value, meta, tone = "" }) {
  return (
    <div className={`kpi ${tone}`}>
      <div className="kpi-head">
        <span>{label}</span>
        <span className="kpi-icon"><Icon /></span>
      </div>
      <strong className="num">{value}</strong>
      <small>{meta}</small>
    </div>
  );
}

// Barres proportionnelles en CSS : lisibles sans bibliothèque de graphiques
function BarList({ items, total }) {
  return (
    <ul className="bar-list">
      {items.map((it) => {
        const pct = total ? (it.count / total) * 100 : 0;
        return (
          <li key={it.label}>
            <div className="bar-row">
              <span>{it.label}</span>
              <strong className="num">{it.count}<small>{total ? ` · ${Math.round(pct)} %` : ""}</small></strong>
            </div>
            <div className="bar" aria-hidden="true"><i className={it.tone} style={{ width: `${it.count ? Math.max(pct, 2) : 0}%` }} /></div>
          </li>
        );
      })}
    </ul>
  );
}

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.admin.stats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBanner title="Chargement impossible" message={error} />;
  if (!stats) return <Loading label="Chargement du tableau de bord…" />;

  const s = stats.par_statut;
  const waiting = s.soumise + s.validee_n1;
  const closed = s.validee + s.refusee + s.refusee_n1;
  const rate = closed ? Math.round((s.validee / closed) * 100) : null;
  const circuit = ["soumise", "validee_n1", "validee", "refusee_n1", "refusee"].map((k) => ({
    label: STATUS[k].label, count: s[k], tone: STATUS[k].tone,
  }));

  return (
    <div>
      <PageHero kicker="Pilotage" title="Tableau de bord"
                lead={`Activité de la plateforme · ${stats.utilisateurs_actifs} compte${stats.utilisateurs_actifs > 1 ? "s" : ""} actif${stats.utilisateurs_actifs > 1 ? "s" : ""}`} />

      <div className="kpi-grid">
        <Kpi icon={IconInbox} label="Demandes" value={stats.total} meta="depuis la mise en service" />
        <Kpi icon={IconClock} label="En attente" value={waiting} tone={stats.en_retard ? "warn" : ""}
             meta={stats.en_retard ? `dont ${stats.en_retard} en attente depuis plus de 48 h` : "aucune en retard"} />
        <Kpi icon={IconFileCheck} label="Validées" value={s.validee}
             meta={rate == null ? "aucune demande clôturée" : `taux de validation : ${rate} %`} />
        <Kpi icon={IconGauge} label="Délai moyen" value={formatDelay(stats.delai_moyen_heures)} meta="de l'envoi à la décision finale" />
      </div>

      <div className="dash-grid">
        <section className="card">
          <div className="card-heading"><div><h2>Circuit de validation</h2><p>Répartition des demandes par statut.</p></div></div>
          <BarList items={circuit} total={stats.total} />
        </section>
        <section className="card">
          <div className="card-heading"><div><h2>Par type d'ouverture</h2><p>Les types les plus demandés.</p></div></div>
          {stats.par_type.length
            ? <BarList items={stats.par_type.map((t) => ({ label: t.label, count: t.count, tone: "ink" }))} total={stats.total} />
            : <p className="muted">Aucune demande pour l'instant.</p>}
        </section>
      </div>

      <section className="table-card">
        <div className="table-card-heading">
          <div>
            <h2>Dernières demandes</h2>
            <p>Les plus récentes, tous statuts confondus.</p>
          </div>
          <Link className="btn btn-secondary btn-sm" to="/admin/demandes">Toutes les demandes<IconArrowRight width={16} height={16} /></Link>
        </div>
        <RequestList rows={stats.recentes} showDemandeur empty="Aucune demande pour l'instant." />
      </section>
    </div>
  );
}
