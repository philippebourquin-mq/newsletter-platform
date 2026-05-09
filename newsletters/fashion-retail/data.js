// fashion-retail/data.js — données placeholder pour tests locaux
// Générées le 2026-05-09

const CONFIG = {
  "slug": "fashion-retail",
  "name": "Fashion & Retail",
  "description": "Veille stratégique · Mode, Maison & Loisirs · Hebdomadaire",
  "status": "active",
  "language": "fr",
  "persona": "Tu analyses l'actualité retail mode et maison pour un responsable achat/merchandising chez Monoprix (division Shopping : Textile, Maison, Loisirs). Ton lecteur suit les tendances retail moyen-de-gamme, la concurrence (Zara, H&M, Primark, La Redoute, Maisons du Monde), les comportements consommateurs et les innovations produit. Il cherche des signaux faibles et des mouvements concurrentiels actionnables.",
  "categories": {
    "tendances": "Tendances produit, couleurs, matières, influences saisonnières textile/maison/loisirs, mouvements de style",
    "concurrence": "Mouvements stratégiques des enseignes concurrentes : lancements, fermetures, partenariats, prix, implantations",
    "consommateur": "Comportement d'achat, études panels, attentes client, évolution du panier moyen, fidélité",
    "retail": "Innovations en point de vente, omnicanalité, e-commerce, logistics, pop-up",
    "durabilite": "Textile responsable, économie circulaire, réglementation, labels et certifications, matières éco-conçues"
  },
  "contenu": {
    "nb_news_principal": 5,
    "nb_news_radar": 5
  },
  "scoring": {
    "poids": {
      "fraicheur": 30,
      "reprise_multi_sources": 25,
      "impact_sectoriel": 20,
      "originalite": 15,
      "engagement_potentiel": 10
    },
    "decroissance_quotidienne_pct": 15,
    "bonus_feedback_pts": 10,
    "score_minimum_backlog": 10
  }
};

const TODAY = {
  "date": "2026-05-09",
  "titre": "Fashion & Retail · 9 mai 2026",
  "news": [
    {
      "id": "fr-001",
      "titre": "Primark accélère son déploiement en France avec 8 ouvertures prévues d'ici fin 2026",
      "categorie": "concurrence",
      "resume": "Le retailer irlandais confirme une vague d'ouvertures ciblant les zones commerciales périurbaines et les retail parks. Après Toulouse-Blagnac et Bordeaux-Mérignac, Primark vise Nantes, Lyon et Strasbourg. La stratégie mise sur des surfaces de 4 000 à 6 000 m² avec une offre textile élargie aux univers Maison et Beauté.",
      "analyse": "Ce déploiement représente une pression directe sur le segment moyen-de-gamme textile. Pour un acheteur Monoprix, le signal fort est l'extension de Primark vers la Maison : catégorie coussin, petit textile déco, bougies — zones où les prix irlandais sont 30 à 40% sous le marché français. À surveiller : les assortiments Maison Primark dans les ouvertures 2026, notamment les lignes saisonnières printemps-été.",
      "sources": ["Retail Gazette", "Fashion Network", "LSA Conso"],
      "score": 91,
      "url": "https://www.retailgazette.co.uk/blog/2026/04/primark-france-expansion/",
      "date": "2026-05-08"
    },
    {
      "id": "fr-002",
      "titre": "Zara teste la livraison J+2 depuis les magasins en France — le store-as-warehouse s'intensifie",
      "categorie": "retail",
      "resume": "Inditex déploie son modèle de ship-from-store dans 45 magasins français, permettant d'expédier les commandes e-commerce directement depuis le stock en rayon. Le délai de livraison tombe à 48h pour 78% des codes postaux français. Le taux de rupture en ligne diminue de 22% selon les données internes citées par Drapers.",
      "analyse": "Le ship-from-store transforme chaque point de vente en mini-entrepôt. L'enjeu pour les acteurs moyen-de-gamme est la nécessité d'unifier les stocks en temps réel entre canal physique et digital. Primark reste volontairement absent de l'e-commerce ; Zara et H&M convergent vers un modèle omnicanal fluide. Question clé : peut-on maintenir un taux de service correct quand le même article peut être vendu simultanément en rayon et en ligne ?",
      "sources": ["Drapers", "Retail Dive"],
      "score": 85,
      "url": "https://www.drapersonline.com/news/inditex-ship-from-store-france-2026",
      "date": "2026-05-07"
    },
    {
      "id": "fr-003",
      "titre": "Le linen et le ramie s'imposent comme matières phares de l'été 2026 selon les panels consommateurs",
      "categorie": "tendances",
      "resume": "L'étude GfK × Fashion Network sur 4 500 consommateurs européens révèle une progression de +38% des recherches pour 'lin naturel' et 'ramie' en textile habillement entre mars et mai 2026. Les couleurs dominantes : blanc naturel, terracotta clair et vert sauge. La gamme de prix acceptée pour un t-shirt en lin oscille entre 18€ et 35€ selon le positionnement de l'enseigne.",
      "analyse": "Signal fort pour la collection estivale et les réassorts : le consommateur cherche activement des alternatives aux fibres synthétiques pour l'été. Le ramie (fibre végétale asiatique moins chère que le lin) ouvre une fenêtre pour un positionnement accessible. À intégrer dans les briefs fournisseur automne-hiver : mix matière avec laine et cachemire recyclé côté Maison (plaids, coussins structurés).",
      "sources": ["Journal du Textile", "Fashion Network", "Just Style"],
      "score": 83,
      "url": "https://fr.fashionnetwork.com/news/lin-ramie-tendances-2026",
      "date": "2026-05-06"
    },
    {
      "id": "fr-004",
      "titre": "La Redoute restructure son pôle Maison et vise 40% du CA sur l'univers déco d'ici 2028",
      "categorie": "concurrence",
      "resume": "La Redoute annonce un plan de 80M€ sur trois ans pour repositionner sa marque Maison face à Maisons du Monde et IKEA. La stratégie inclut le lancement de collections capsule avec des designers français, un catalogue éco-conçu et une extension du réseau de points relais pour les articles volumineux. Le site Redoute.fr représente déjà 65% des ventes totales.",
      "analyse": "La Redoute quitte le positionnement généraliste pour devenir un acteur spécialisé Maison premium-accessible. Ce mouvement comprime l'espace disponible pour les enseignes de centre-ville moyen-de-gamme. La force de La Redoute : un fichier client établi, une logistique pièce unique maîtrisée, et une notoriété hors ligne qui reste solide au-delà de 40 ans. À surveiller : les prix de lancement des collections designer (signal de prix plafond accepté en déco).",
      "sources": ["LSA Conso", "e-commerce Mag"],
      "score": 79,
      "url": "https://www.lsa-conso.fr/la-redoute-plan-maison-2028",
      "date": "2026-05-05"
    },
    {
      "id": "fr-005",
      "titre": "Règlement européen ESPR : les exigences écoconception s'étendent au textile moyen-de-gamme dès 2027",
      "categorie": "durabilite",
      "resume": "La Commission européenne publie les actes délégués ESPR (Ecodesign for Sustainable Products Regulation) pour le textile : durabilité minimale de 30 lavages pour les articles > 30€, obligation de fiche numérique produit (Digital Product Passport) dès 2027, et interdiction de destruction des invendus habillement. Les retailers ont jusqu'au 1er janvier 2027 pour se conformer.",
      "analyse": "Pour le segment moyen-de-gamme (15€-60€), l'ESPR change fondamentalement les briefs fournisseur. Le seuil de 30 lavages à 30€ va concerner la majorité des références textile. Cela impose des tests qualité plus stricts, une documentation matière plus poussée et une revue des conditions de sourcing. Côté opportunité : le DPP textile peut devenir un argument marketing différenciant si on le rend visible côté client (QR code, application).",
      "sources": ["Journal du Textile", "Just Style"],
      "score": 77,
      "url": "https://www.journaldutextile.com/reglementation/espr-textile-2027",
      "date": "2026-05-04"
    }
  ],
  "radar": [
    {
      "id": "fr-r001",
      "titre": "H&M annonce une ligne maison premium 'H&M Home Signature' à lancer en septembre",
      "categorie": "concurrence",
      "resume": "Montée en gamme confirmée de H&M sur le textile déco : prix médian prévu à 49€ vs 22€ actuellement.",
      "score": 68
    },
    {
      "id": "fr-r002",
      "titre": "Shein ouvre un showroom physique à Paris Marais — test du modèle phygital",
      "categorie": "retail",
      "resume": "Shein teste le format pop-up permanent avec retrait en magasin des commandes en ligne. Le showroom ne stocke pas : tout est commandé via appli et livré sous 48h.",
      "score": 65
    },
    {
      "id": "fr-r003",
      "titre": "Les ventes de pyjamas et vêtements d'intérieur progressent de +18% sur un an",
      "categorie": "consommateur",
      "resume": "Le marché du 'homewear' confirme sa solidité post-Covid. Lingerie de nuit confortable et bas de pyjama unisexe sont les références les plus dynamiques.",
      "score": 62
    },
    {
      "id": "fr-r004",
      "titre": "Maisons du Monde teste la seconde main intégrée en magasin via Vestiaire Collective",
      "categorie": "durabilite",
      "resume": "Partenariat pilote dans 12 magasins : un coin dépôt-vente pour les meubles et objets de décoration d'occasion, avec valorisation crédit fidélité.",
      "score": 58
    },
    {
      "id": "fr-r005",
      "titre": "Le coloris 'écorce' (brun rosé chaud) désigné couleur de saison par les instituts de tendance",
      "categorie": "tendances",
      "resume": "WGSN et Pantone convergent sur une palette de bruns chauds pour AH2026-27. Écorce, cannelle claire et noisette domineront les collections textiles et déco.",
      "score": 55
    }
  ]
};

const ARCHIVE = [
  {
    "date": "2026-05-02",
    "titre": "Fashion & Retail · 2 mai 2026",
    "news_count": 5,
    "radar_count": 5,
    "titres": [
      "Uniqlo veut atteindre 100 magasins en France d'ici 2030, accélération confirmée",
      "Le live shopping explose en France : +120% de GMV sur un an selon Fevad",
      "Laine mérinos recyclée : les marques moyen-de-gamme se l'approprient",
      "Zalando lance un abonnement premium avec livraison illimitée à 6,99€/mois",
      "Loi AGEC : les entreprises textile en retard sur l'affichage environnemental"
    ]
  },
  {
    "date": "2026-04-25",
    "titre": "Fashion & Retail · 25 avril 2026",
    "news_count": 5,
    "radar_count": 5,
    "titres": [
      "Primark confirme un CA de 9,5 Mds£ sur l'exercice 2025-26, croissance de +12%",
      "Le drop (lancement limité) s'étend au segment moyen-de-gamme",
      "GfK : le panier textile moyen recule de 4% en volume mais tient en valeur",
      "Decathlon entre sur le marché du textile lifestyle — signal de diversification",
      "Coton BCI : les certifications durables peinent encore à séduire le consommateur"
    ]
  },
  {
    "date": "2026-04-18",
    "titre": "Fashion & Retail · 18 avril 2026",
    "news_count": 5,
    "radar_count": 5,
    "titres": [
      "H&M Group publie des résultats T1 en hausse : la stratégie multi-marques porte ses fruits",
      "Le vêtement outdoor casual devient la nouvelle norme de bureau",
      "Amazon Fashion consolide sa position n°2 du e-commerce textile en France",
      "Etsy et Vinted confirment la montée du marché secondaire sur la déco maison",
      "Matériaux biosourcés : Econyl et Tencel intègrent les offres grande distribution"
    ]
  }
];

const ARCHIVE_FULL = {
  "2026-05-02": {
    "date": "2026-05-02",
    "titre": "Fashion & Retail · 2 mai 2026",
    "news": [
      {
        "id": "fr-0502-001",
        "titre": "Uniqlo veut atteindre 100 magasins en France d'ici 2030, accélération confirmée",
        "categorie": "concurrence",
        "resume": "Fast Retailing confirme lors de son AG que la France est désignée marché prioritaire en Europe. Après 27 magasins actuels, Uniqlo vise 10 ouvertures par an, ciblant les villes moyennes (>80 000 hab.) et les centres commerciaux régionaux. La marque se différencie par la technologie matière (HeatTech, AIRism) et une proposition qualité-prix très construite.",
        "analyse": "Uniqlo joue dans une case proche du positionnement Monoprix Shopping : qualité perçue au-dessus de H&M, prix accessibles, basics bien exécutés. L'accélération sur les villes moyennes est le signal le plus intéressant — c'est précisément la zone de chalandise où Monoprix est fort. À surveiller : les prix d'entrée Uniqlo sur le jersey et le basics coton vs les offres propriétaires.",
        "sources": ["Fashion Network", "Journal du Textile"],
        "score": 88,
        "url": "https://fr.fashionnetwork.com/news/uniqlo-france-100-magasins-2030",
        "date": "2026-05-01"
      },
      {
        "id": "fr-0502-002",
        "titre": "Le live shopping explose en France : +120% de GMV sur un an selon Fevad",
        "categorie": "retail",
        "resume": "La Fédération e-commerce publie une étude montrant que le live shopping a généré 1,2Md€ de ventes en 2025 en France. Le textile et la maison représentent 45% du total. TikTok Shop, Instagram Live et les plateformes dédiées progressent fortement. Le taux de conversion moyen d'un live est 3x supérieur à celui d'une page produit statique.",
        "analyse": "Le live shopping change la dynamique de découverte produit. En textile maison, les produits avec texture intéressante (velours, maille épaisse) et les articles de déco colorés performent. Le canal impose de repenser le contenu produit et la gestion des pics de commande.",
        "sources": ["e-commerce Mag", "Retail Dive"],
        "score": 82,
        "url": "https://www.e-commercemag.fr/live-shopping-fevad-2025-bilan",
        "date": "2026-04-30"
      },
      {
        "id": "fr-0502-003",
        "titre": "Laine mérinos recyclée : les marques moyen-de-gamme se l'approprient",
        "categorie": "tendances",
        "resume": "Des marques comme Arket, Cos et désormais H&M Selected intègrent de la laine mérinos recyclée (provenant de fils post-industriels) dans leurs collections automne 2026. Le prix d'un pull passe de 25€ à 45€ avec labellisation RWS + recyclé. Les consommateurs de 28-45 ans acceptent la survaleur selon les tests consommateur menés par Just Style.",
        "analyse": "La laine mérinos recyclée ouvre un corridor de prix intéressant pour le moyen-de-gamme : justifier une montée à 40-50€ sur un pull, là où le segment était bloqué à 30€. Opportunité pour les collections AH2026 : lancer 2-3 références clés avec communication matière.",
        "sources": ["Just Style", "Journal du Textile"],
        "score": 79,
        "url": "https://www.just-style.com/analysis/merino-wool-recycled-mid-market",
        "date": "2026-04-29"
      },
      {
        "id": "fr-0502-004",
        "titre": "Zalando lance un abonnement premium avec livraison illimitée à 6,99€/mois",
        "categorie": "retail",
        "resume": "Zalando Plus devient 'Zalando Premium' à 6,99€/mois : livraison et retour illimités, accès prioritaire aux soldes, recommandations personnalisées. La plateforme compte 17M d'abonnés actifs en Europe. En France, l'abonnement vise à fidéliser les 3,5M d'utilisateurs mensuels.",
        "analyse": "Zalando accélère son modèle de fidélisation par abonnement, à la manière d'Amazon Prime. Pour les enseignes physiques, la menace est la captation des achats impulsifs textile : l'abonné commande plus souvent, avec moins de friction. Le contre-argument : l'expérience en magasin reste différenciante pour l'entrée dans une nouvelle catégorie produit.",
        "sources": ["Retail Week", "e-commerce Mag"],
        "score": 75,
        "url": "https://www.retail-week.com/zalando-premium-subscription-europe",
        "date": "2026-04-28"
      },
      {
        "id": "fr-0502-005",
        "titre": "Loi AGEC : les entreprises textile en retard sur l'affichage environnemental",
        "categorie": "durabilite",
        "resume": "Un rapport du Ministère de la Transition Écologique révèle que 60% des retailers textile n'ont pas encore mis en place l'affichage environnemental obligatoire prévu par la loi AGEC. Les amendes (jusqu'à 15 000€ par référence) n'ont pas encore été activées, mais les inspections sont annoncées dès le S2 2026.",
        "analyse": "Pour les acheteurs-merchandiseurs, ce rapport est un signal d'alarme opérationnel. L'affichage environnemental (score A à E) exige une remontée de données fournisseur que beaucoup n'ont pas encore. Priorité : auditer les fournisseurs top 20 sur leur capacité à fournir les données d'affichage.",
        "sources": ["Journal du Textile", "LSA Conso"],
        "score": 73,
        "url": "https://www.journaldutextile.com/reglementation/agec-affichage-retard-2026",
        "date": "2026-04-27"
      }
    ],
    "radar": [
      {
        "id": "fr-0502-r001",
        "titre": "Vinted dépasse 100M€ de revenus en France pour la première fois",
        "categorie": "consommateur",
        "resume": "Le marché secondaire s'installe comme un canal d'achat permanent, y compris pour le textile maison.",
        "score": 65
      },
      {
        "id": "fr-0502-r002",
        "titre": "IKEA teste des abonnements location de meubles en Suisse et Pays-Bas",
        "categorie": "retail",
        "resume": "Le modèle location meuble (22€/mois pour un canapé) interroge le modèle propriété dans la maison.",
        "score": 60
      },
      {
        "id": "fr-0502-r003",
        "titre": "Le marché du loungewear reste dynamique : +9% vs 2025",
        "categorie": "tendances",
        "resume": "Les ensembles coordonnés intérieur-extérieur confirment leur ancrage dans les comportements.",
        "score": 57
      },
      {
        "id": "fr-0502-r004",
        "titre": "Primark lancera sa première collection 100% matières certifiées en été 2026",
        "categorie": "durabilite",
        "resume": "Engagement RSE : coton BCI et polyester recyclé sur la totalité d'une gamme basique.",
        "score": 54
      },
      {
        "id": "fr-0502-r005",
        "titre": "Les Galeries Lafayette testent le 'rendez-vous styliste' payant en magasin",
        "categorie": "retail",
        "resume": "Service de personal shopping premium à 49€/h avec recommandations personnalisées multi-marques.",
        "score": 50
      }
    ]
  }
};
