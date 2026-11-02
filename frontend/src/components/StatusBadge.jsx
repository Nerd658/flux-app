// Statuts : libellé, ton visuel et position dans le circuit de validation
export const STATUS = {
  soumise: { label: "En attente Manager", tone: "wait", step: 0 },
  validee_manager: { label: "En attente Technique", tone: "wait", step: 1 },
  validee_technique: { label: "En attente RSSI", tone: "wait", step: 2 },
  validee: { label: "Validée", tone: "ok", step: 3 },
  refusee: { label: "Refusée", tone: "ko", step: -1 },
  validee_n1: { label: "En attente validation", tone: "wait", step: 1 },
  refusee_n1: { label: "Refusée", tone: "ko", step: -1 },
};

// Regroupements utilisés par les filtres des listes
export const STATUS_GROUPS = [
  { key: "all", label: "Toutes", meta: "demandes envoyées", match: () => true },
  { key: "wait", label: "En cours", meta: "en attente de validation", match: (s) => STATUS[s]?.tone === "wait" },
  { key: "ok", label: "Validées", meta: "PDF disponible", match: (s) => s === "validee" },
  { key: "ko", label: "Refusées", meta: "à corriger", match: (s) => STATUS[s]?.tone === "ko" },
];

const PILL = { wait: "status-wait", ok: "status-up", ko: "status-down" };

export default function StatusBadge({ statut }) {
  const s = STATUS[statut] || { label: statut, tone: "" };
  return <span className={`status-pill ${PILL[s.tone] || ""}`}>{s.label}</span>;
}

// Mini-progression du circuit : soumission, Manager, Technique, RSSI
export function MiniProgress({ statut }) {
  const s = STATUS[statut] || { step: 0, tone: "wait" };
  const states = [0, 1, 2, 3].map((i) => {
    if (i === 0) return "done";
    const level = i - 1; // 0 = Manager, 1 = Technique, 2 = RSSI
    if (s.tone === "ko" && s.step === level) return "ko";
    if (s.tone === "ok" || s.step > level) return "done";
    if (s.tone === "wait" && s.step === level) return "current";
    return "";
  });
  return (
    <span className="mini-progress" aria-hidden="true">
      {states.map((st, i) => <i key={i} className={st} />)}
    </span>
  );
}
