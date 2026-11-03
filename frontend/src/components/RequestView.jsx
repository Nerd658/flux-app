// Contenu d'une demande : en-tête (personnes, période) puis flux sous forme de routes et tableau officiel
import FlowRoute from "./FlowRoute.jsx";
import { daysBetween, formatDate } from "./ui.jsx";

const STATUT_PRO_LABELS = {
  employe: "Employé",
  prestataire: "Prestataire",
  stagiaire: "Stagiaire",
};

function Person({ title, p, statut }) {
  return (
    <div className="person">
      <span className="person-title">{title}</span>
      <strong>{p.prenom} {p.nom.toUpperCase()}</strong>
      {statut && <span className="person-badge" style={{ fontSize: "0.8rem", color: "#175cd3", fontWeight: 500 }}>{STATUT_PRO_LABELS[statut] || statut}</span>}
      <span>{p.email}</span>
      <span className="num">{p.telephone}</span>
    </div>
  );
}

export default function RequestView({ req }) {
  const tmp = req.periode === "temporaire";
  return (
    <div className="request-view">
      <section className="facts">
        <Person title="Demandeur" p={req.demandeur} statut={req.demandeur?.statut_pro} />
        <Person title={req.manager_cuid ? `Manager (${req.manager_cuid})` : "Manager"} p={req.manager} />
        <div className="person">
          <span className="person-title">Direction</span>
          <strong>{req.departement}</strong>
          <span>Type d'ouverture : {req.flux_type}</span>
        </div>
        <div className="person">
          <span className="person-title">Période {tmp ? "temporaire" : "permanente"}</span>
          <strong>{tmp ? `${formatDate(req.date_debut)} au ${formatDate(req.date_fin)}` : `À partir du ${formatDate(req.date_debut)}`}</strong>
          <span>{tmp ? `${daysBetween(req.date_debut, req.date_fin)} jours` : "Sans date de fin"}</span>
        </div>
        {req.ticket_ref && (
          <div className="person">
            <span className="person-title">Ticket Oline</span>
            <strong className="num">{req.ticket_ref}</strong>
            <span>Créé automatiquement</span>
          </div>
        )}
      </section>

      <section>
        <h3 className="section-title">Flux demandés ({req.lines.length})</h3>
        <ol className="flow-list">
          {req.lines.map((l) => (
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
      </section>
    </div>
  );
}
