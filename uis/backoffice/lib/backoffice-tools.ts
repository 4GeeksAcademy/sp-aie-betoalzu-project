export const toolGroups = [
  {
    id: 'talento',
    name: 'Talento',
    description: 'Las personas, en el centro.',
    tools: [
      {
        name: 'Talent Pipeline Tracker',
        description: 'Organiza candidaturas, etapas y notas de seguimiento del equipo de selección.',
        href: '/talent-pipeline-tracker',
        initials: 'TP',
      },
    ],
  },
  {
    id: 'operaciones',
    name: 'Operaciones',
    description: 'Todo lo que hace que el día a día funcione.',
    tools: [
      {
        name: 'Inventario',
        description: 'Gestiona productos, entradas, salidas e historial de pedidos.',
        href: '/inventory/products',
        initials: 'IN',
      },
      {
        name: 'Gestor de incidencias',
        description: 'Registra, clasifica y sigue las incidencias técnicas, operativas y de clientes.',
        href: '/incidents',
        initials: 'GI',
      },
      {
        name: 'Analizador de incidentes',
        description: 'Valida archivos CSV de tickets, detecta errores y exporta un resumen operativo.',
        href: '/incident-analyzer',
        initials: 'AI',
      },
      {
        name: 'Proveedores',
        description: 'Consulta y administra proveedores y su estado de actividad.',
        href: '/suppliers',
        initials: 'PR',
      },
      {
        name: 'Chat de soporte',
        description: 'Accede al chat de soporte en tiempo real.',
        href: '/chat',
        initials: 'CS',
      },
    ],
  },
  {
    id: 'comercial',
    name: 'Comercial',
    description: 'Conocimiento y oportunidades, conectados.',
    tools: [
      {
        name: 'Base de conocimiento',
        description: 'Consulta servicios, precios, SLA y procesos comerciales con el asistente RAG.',
        href: '/knowledge',
        initials: 'BC',
      },
      {
        name: 'Recepción de RFP',
        description: 'Recibe solicitudes PDF y consulta el análisis y estado de cada ticket.',
        href: '/rfp-intake',
        initials: 'RF',
      },
    ],
  },
  {
    id: 'reporting',
    name: 'Análisis y seguimiento',
    description: 'Una visión más clara de la operación.',
    tools: [
      {
        name: 'Reporte semanal',
        description: 'Consulta el informe semanal de la operación.',
        href: '/reporting',
        initials: 'RS',
      },
      {
        name: 'Telemetría técnica',
        description: 'Revisa volumen, errores y fallos de autenticación del sistema por día.',
        href: '/telemetry',
        initials: 'TT',
      },
    ],
  },
];
