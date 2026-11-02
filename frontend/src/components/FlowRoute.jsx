// Élément signature : représentation d'un flux sous forme de route Source → protocole/ports → Destination
export function connectorLabel(l) {
  return [l.protocole?.trim().toUpperCase(), l.dst_ports?.trim()].filter(Boolean).join(" ") || "…";
}

export default function FlowRoute({ line, compact = false }) {
  return (
    <div className={`route ${compact ? "compact" : ""}`}>
      <div className="route-end">
        <span className="route-role">Source</span>
        <strong className="num">{line.src_ip || "—"}</strong>
        <span className="route-meta">{[line.src_zone, line.src_app].filter(Boolean).join(" · ") || "Zone, application"}</span>
      </div>
      <div className="route-link" aria-label={`via ${connectorLabel(line)}`}>
        <span className="route-proto num">{connectorLabel(line)}</span>
      </div>
      <div className="route-end dst">
        <span className="route-role">Destination</span>
        <strong className="num">{line.dst_ip || "—"}</strong>
        <span className="route-meta">{[line.dst_zone, line.dst_app].filter(Boolean).join(" · ") || "Zone, application"}</span>
      </div>
    </div>
  );
}
