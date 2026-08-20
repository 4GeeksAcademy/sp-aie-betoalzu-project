export const VALID_CATEGORIES = ['TECHNICAL', 'BILLING', 'ACCESS', 'HR_QUERY', 'COMPLAINT'] as const;
export const VALID_STATUSES = ['OPEN', 'CLOSED', 'DISCARDED'] as const;

const REQUIRED_HEADERS = [
  'ticket_id',
  'date',
  'client_company',
  'category',
  'description',
  'agent_id',
  'status',
  'customer_email',
  'satisfaction_score',
] as const;

const AGENT_ID_PATTERN = /^AGT-\d{2}$/;

export type IncidentInvalidRules = {
  missing_client_company: number;
  invalid_category: number;
  invalid_description: number;
  invalid_agent: number;
  invalid_status: number;
  invalid_email: number;
  closed_no_score: number;
  score_out_of_range: number;
};

export type AnalysisResult = {
  source_file: string;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_rules: IncidentInvalidRules;
  categories: Record<string, number>;
  statuses: Record<string, number>;
  scores: Record<number, number>;
};

export type IncidentSummary = {
  source_file: string;
  total_records: number;
  valid_records: number;
  invalid_records: number;
  invalid_rules: IncidentInvalidRules;
  categories: Record<string, number>;
  statuses: Record<string, number>;
  scores: Record<string, number>;
  closed_tickets: number;
  scored_tickets: number;
  average_score: number;
};

export class CsvAnalysisError extends Error {
  statusCode: number;

  constructor(message: string, statusCode: number) {
    super(message);
    this.statusCode = statusCode;
  }
}

let lastAnalysis: AnalysisResult | null = null;

function clean(value: string | undefined) {
  return (value || '').trim();
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = '';
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"') {
      if (inQuotes && next === '"') {
        value += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === ',' && !inQuotes) {
      row.push(value);
      value = '';
      continue;
    }

    if ((ch === '\n' || ch === '\r') && !inQuotes) {
      if (ch === '\r' && next === '\n') i += 1;
      row.push(value);
      value = '';
      if (row.some((cell) => cell.length > 0)) rows.push(row);
      row = [];
      continue;
    }

    value += ch;
  }

  if (value.length > 0 || row.length > 0) {
    row.push(value);
    if (row.some((cell) => cell.length > 0)) rows.push(row);
  }

  return rows;
}

function createEmptyInvalidRules(): IncidentInvalidRules {
  return {
    missing_client_company: 0,
    invalid_category: 0,
    invalid_description: 0,
    invalid_agent: 0,
    invalid_status: 0,
    invalid_email: 0,
    closed_no_score: 0,
    score_out_of_range: 0,
  };
}

function buildRowsMap(headers: string[], values: string[]): Record<string, string> {
  const row: Record<string, string> = {};
  for (let i = 0; i < headers.length; i += 1) {
    row[headers[i]] = values[i] ?? '';
  }
  return row;
}

export function analyzeCsvText(text: string, sourceFile: string): AnalysisResult {
  if (!text.trim()) {
    throw new CsvAnalysisError('El fichero CSV esta vacio.', 400);
  }

  const parsedRows = parseCsv(text.replace(/^\uFEFF/, ''));
  if (!parsedRows.length) {
    throw new CsvAnalysisError('El fichero CSV esta vacio o no contiene cabecera.', 400);
  }

  const headers = parsedRows[0].map((cell) => clean(cell));
  const missingHeaders = REQUIRED_HEADERS.filter((header) => !headers.includes(header));
  if (missingHeaders.length) {
    throw new CsvAnalysisError(
      `El fichero CSV no tiene el formato esperado. Faltan columnas requeridas: ${missingHeaders.join(', ')}`,
      422,
    );
  }

  const invalidRules = createEmptyInvalidRules();
  const categories = Object.fromEntries(VALID_CATEGORIES.map((k) => [k, 0]));
  const statuses = Object.fromEntries(VALID_STATUSES.map((k) => [k, 0]));
  const scores: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };

  let totalRecords = 0;
  let validRecords = 0;

  for (let i = 1; i < parsedRows.length; i += 1) {
    const rowValues = parsedRows[i];
    if (rowValues.length === 1 && clean(rowValues[0]) === '') continue;

    totalRecords += 1;
    const row = buildRowsMap(headers, rowValues);
    const rowErrors: Array<keyof IncidentInvalidRules> = [];

    const clientCompany = clean(row.client_company);
    const category = clean(row.category);
    const description = clean(row.description);
    const agentId = clean(row.agent_id);
    const status = clean(row.status);
    const customerEmail = clean(row.customer_email);
    const rawScore = clean(row.satisfaction_score);

    if (!clientCompany) rowErrors.push('missing_client_company');
    if (!VALID_CATEGORIES.includes(category as (typeof VALID_CATEGORIES)[number])) rowErrors.push('invalid_category');
    if (description.length < 5) rowErrors.push('invalid_description');
    if (!AGENT_ID_PATTERN.test(agentId)) rowErrors.push('invalid_agent');
    if (!VALID_STATUSES.includes(status as (typeof VALID_STATUSES)[number])) rowErrors.push('invalid_status');
    if (!customerEmail || !customerEmail.includes('@')) rowErrors.push('invalid_email');

    let scoreValue: number | null = null;
    if (status === 'CLOSED' && !rawScore) rowErrors.push('closed_no_score');

    if (rawScore) {
      const parsedScore = Number(rawScore);
      if (!Number.isInteger(parsedScore) || parsedScore < 1 || parsedScore > 5) {
        rowErrors.push('score_out_of_range');
      } else {
        scoreValue = parsedScore;
      }
    }

    if (rowErrors.length) {
      rowErrors.forEach((rule) => {
        invalidRules[rule] += 1;
      });
      continue;
    }

    validRecords += 1;
    categories[category] += 1;
    statuses[status] += 1;
    if (status === 'CLOSED' && scoreValue !== null) scores[scoreValue] += 1;
  }

  return {
    source_file: sourceFile,
    total_records: totalRecords,
    valid_records: validRecords,
    invalid_records: totalRecords - validRecords,
    invalid_rules: invalidRules,
    categories,
    statuses,
    scores,
  };
}

export function buildSummary(result: AnalysisResult): IncidentSummary {
  const closedTickets = result.statuses.CLOSED || 0;
  const scoredTickets = Object.values(result.scores).reduce((acc, value) => acc + value, 0);
  const averageScore =
    scoredTickets > 0
      ? Object.entries(result.scores).reduce((acc, [score, count]) => acc + Number(score) * count, 0) / scoredTickets
      : 0;

  return {
    source_file: result.source_file,
    total_records: result.total_records,
    valid_records: result.valid_records,
    invalid_records: result.invalid_records,
    invalid_rules: result.invalid_rules,
    categories: result.categories,
    statuses: result.statuses,
    scores: {
      '1': result.scores[1] || 0,
      '2': result.scores[2] || 0,
      '3': result.scores[3] || 0,
      '4': result.scores[4] || 0,
      '5': result.scores[5] || 0,
    },
    closed_tickets: closedTickets,
    scored_tickets: scoredTickets,
    average_score: Number(averageScore.toFixed(2)),
  };
}

export function buildMetricsCsv(result: AnalysisResult): string {
  const summary = buildSummary(result);
  const rows: Array<[string, string | number]> = [
    ['total_records', summary.total_records],
    ['valid_records', summary.valid_records],
    ['invalid_records', summary.invalid_records],
  ];

  Object.entries(summary.invalid_rules).forEach(([rule, count]) => rows.push([`invalid_${rule}`, count]));
  Object.entries(summary.categories).forEach(([key, count]) => rows.push([`category_${key}`, count]));
  Object.entries(summary.statuses).forEach(([key, count]) => rows.push([`status_${key}`, count]));

  rows.push(['closed_tickets', summary.closed_tickets]);
  rows.push(['scored_tickets', summary.scored_tickets]);
  rows.push(['average_score', summary.average_score.toFixed(2)]);

  Object.entries(summary.scores).forEach(([score, count]) => rows.push([`score_${score}`, count]));

  const body = rows.map(([metric, value]) => `${metric},${value}`).join('\n');
  return `metric,value\n${body}\n`;
}

export function setLastAnalysis(result: AnalysisResult) {
  lastAnalysis = result;
}

export function getLastAnalysis() {
  return lastAnalysis;
}