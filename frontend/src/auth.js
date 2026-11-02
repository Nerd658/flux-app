// Session et rôles partagés (module sans JSX : évite les imports circulaires avec App.jsx)
import { createContext, useContext } from "react";

export const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export const VALIDATOR_ROLES = ["manager", "securite", "rssi"];

// Chaque rôle est décrit à l'utilisateur : il sait ce qu'il peut faire (et ne pas faire)
export const ROLE_INFO = {
  demandeur: {
    label: "Demandeur",
    desc: "Vous créez et suivez vos demandes d'ouverture de flux.",
  },
  manager: {
    label: "Manager",
    desc: "Vous validez les demandes d'ouverture de flux de votre département (Niveau 1).",
  },
  securite: {
    label: "Validateur Technique",
    desc: "Vous validez la conformité technique sécurité des demandes (Niveau 2).",
  },
  rssi: {
    label: "RSSI",
    desc: "Vous apportez la validation finale de sécurité (Niveau 3).",
  },
  admin: {
    label: "Administrateur",
    desc: "Vous gérez les comptes, les référentiels et le journal d'audit. Vous ne validez aucune demande.",
  },
};

export const ROLE_LABELS = Object.fromEntries(Object.entries(ROLE_INFO).map(([k, v]) => [k, v.label]));

export function homeFor(user) {
  if (user.role === "demandeur") return "/mes-demandes";
  if (user.role === "admin") return "/admin";
  return "/validation";
}

export function displayName(u) {
  if (!u) return "";
  if (u.prenom && u.prenom !== "-") {
    return u.nom && u.nom !== "-" && u.nom !== u.cuid ? `${u.prenom} ${u.nom}` : u.prenom;
  }
  return u.nom && u.nom !== "-" ? u.nom : u.cuid || "";
}

export const initials = (u) => {
  if (!u) return "";
  const first = u.prenom && u.prenom !== "-" ? u.prenom[0] : "";
  const last = u.nom && u.nom !== "-" && u.nom !== u.cuid ? u.nom[0] : (u.cuid ? u.cuid[0] : "");
  return `${first}${last}`.toUpperCase() || u.cuid?.slice(0, 2).toUpperCase() || "";
};

export const fullName = (u) => {
  if (!u) return "";
  if (u.prenom && u.prenom !== "-") {
    return `${u.prenom} ${u.nom.toUpperCase()}`;
  }
  return u.nom && u.nom !== "-" ? u.nom.toUpperCase() : u.cuid || "";
};
