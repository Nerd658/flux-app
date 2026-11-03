import { useNavigate } from "react-router-dom";
import StatusBadge, { MiniProgress } from "./StatusBadge.jsx";
import { formatDateTime, Loading } from "./ui.jsx";

export default function RequestList({ rows, empty, emptyHint, emptyAction, showDemandeur = false }) {
  const navigate = useNavigate();
  if (!rows) return <Loading label="Chargement des demandes…" />;
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <strong>{empty}</strong>
        {emptyHint && <small>{emptyHint}</small>}
        {emptyAction}
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="requests-table">
        <thead>
          <tr>
            <th>Référence</th>
            <th>Type</th>
            {showDemandeur && <th>Demandeur</th>}
            <th className="r">Flux</th>
            <th>Soumise le</th>
            <th>Circuit</th>
            <th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            // Ligne entièrement cliquable, et accessible au clavier via le lien de référence
            <tr key={r.id} onClick={() => navigate(`/demandes/${r.id}`)}>
              <td>
                <a className="ref ip-cell" href={`/demandes/${r.id}`} onClick={(e) => { e.preventDefault(); navigate(`/demandes/${r.id}`); }}>{r.reference}</a>
                {r.ticket_ref && <div><span className="ticket-pill-sm" title={`Ticket Oline : ${r.ticket_ref}`}>{r.ticket_ref}</span></div>}
              </td>
              <td>{r.flux_type}</td>
              {showDemandeur && <td>{r.demandeur}</td>}
              <td className="r num">{r.nb_lignes}</td>
              <td className="num">{formatDateTime(r.created_at)}</td>
              <td><MiniProgress statut={r.statut} /></td>
              <td><StatusBadge statut={r.statut} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
