'use client';

import { useEffect, useState } from 'react';
import {
  decideRfpApproval,
  downloadFinalRfpDocument,
  generateRfpResponses,
  getRfpTicket,
  listRfpTickets,
  retryRfpTicket,
  resumeRfpApprovalRevision,
  startRfpApprovals,
  uploadRfp,
  type RfpApprovalAction,
} from '@/services/rfp-intake';
import type {
  RfpMetadata,
  RfpTicketDetail,
  RfpTicketSummary,
} from '@/types/rfp-intake';

const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

const STATUS_LABELS: Record<RfpTicketSummary['status'], string> = {
  analizando: 'Analizando',
  descartado: 'Descartado',
  analisis_completo: 'Análisis completo',
  generando_borrador: 'Generando secciones',
  'en-evaluación': 'Evaluando secciones',
  needs_human_review: 'Requiere revisión humana',
  'esperando_aprobación': 'Esperando aprobación',
  terminado: 'Terminado',
};

const APPROVER_NAMES: Record<string, string> = {
  seleccion: 'Javier Almeida',
  capacitacion: 'Elena Vargas',
  soporte: 'Roberto Díaz',
};

function display(value: string | null | undefined): string {
  return value?.trim() || 'No especificado';
}

function MetadataCard({ metadata }: { metadata: RfpMetadata }) {
  const rows = [
    ['Cliente', metadata.client_name],
    ['Sede', metadata.client_hq === 'no_especificado' ? null : metadata.client_hq],
    ['Servicio solicitado', metadata.services_requested.join(', ') || null],
    ['Alcance', metadata.scope],
    ['Fecha límite', metadata.deadline],
    ['Presupuesto', metadata.budget_range],
    ['Moneda derivada', metadata.currency],
    ['Departamentos activos', metadata.departments_needed.join(', ') || null],
  ];

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-lg font-bold text-slate-900">Datos extraídos</h3>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {label}
            </dt>
            <dd className="mt-1 whitespace-pre-wrap text-sm text-slate-800">
              {display(value)}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-5 border-t border-slate-100 pt-4">
        <h4 className="text-sm font-bold text-slate-800">Legibilidad del documento</h4>
        <p className="mt-1 text-sm text-slate-600">
          {metadata.readability_metrics.word_count ?? 0} palabras ·{' '}
          {metadata.readability_metrics.sentence_count ?? 0} oraciones · idioma{' '}
          {metadata.readability_metrics.language ?? 'no determinado'}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {metadata.readability_metrics.limitation ?? 'Métricas orientativas; no representan un coste monetario.'}
        </p>
      </div>
      {metadata.open_questions.length > 0 && (
        <div className="mt-5 rounded-lg bg-amber-50 p-4">
          <h4 className="text-sm font-bold text-amber-900">Datos pendientes de Ventas</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">
            {metadata.open_questions.map((question, index) => (
              <li key={`${question}-${index}`}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

type TicketResultProps = {
  ticket: RfpTicketDetail;
  busy: boolean;
  comments: Record<string, string>;
  onGenerate: () => void;
  onStartApprovals: () => void;
  onResumeApproval: (departmentId: string) => void;
  onCommentChange: (departmentId: string, value: string) => void;
  onDecision: (departmentId: string, action: RfpApprovalAction) => void;
  onDownload: () => void;
};

function TicketResult({
  ticket,
  busy,
  comments,
  onGenerate,
  onStartApprovals,
  onResumeApproval,
  onCommentChange,
  onDecision,
  onDownload,
}: TicketResultProps) {
  if (ticket.status === 'descartado') {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h3 className="text-lg font-bold text-amber-900">Documento descartado</h3>
        <p className="mt-2 text-sm text-amber-900">{ticket.classification?.reason}</p>
        {ticket.classification?.evidence && (
          <blockquote className="mt-3 border-l-2 border-amber-400 pl-3 text-sm text-amber-800">
            Evidencia: {ticket.classification.evidence}
          </blockquote>
        )}
      </section>
    );
  }

  if (!ticket.metadata) return null;

  return (
    <>
      <MetadataCard metadata={ticket.metadata} />
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            {ticket.status === 'analisis_completo'
              ? 'Aspectos por departamento'
              : 'Secciones de propuesta'}
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Solo aparecen los departamentos activos en el handoff de esta RFP.
          </p>
        </div>
        {ticket.status === 'analisis_completo' && ticket.can_generate && (
          <button
            type="button"
            onClick={onGenerate}
            disabled={busy}
            className="mt-4 rounded-full bg-brand px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
          >
            {busy ? 'Iniciando...' : 'Generar secciones de propuesta'}
          </button>
        )}
        {ticket.status === 'en-evaluación' && ticket.processing && (
          <p role="status" className="mt-4 text-sm text-slate-600">
            Las secciones están en evaluación.
          </p>
        )}
        {['en-evaluación', 'needs_human_review'].includes(ticket.status) &&
          !ticket.processing && (
            <button
              type="button"
              onClick={onStartApprovals}
              disabled={busy}
              className="mt-4 rounded-full bg-brand px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
            >
              {busy ? 'Preparando...' : 'Iniciar revisión y aprobaciones'}
            </button>
          )}
        {ticket.status === 'generando_borrador' && (
          <p role="status" className="mt-4 text-sm text-slate-600">
            Se están generando o revisando las secciones.
          </p>
        )}
        {ticket.status === 'esperando_aprobación' && (
          <p role="status" className="mt-4 text-sm text-slate-600">
            Las decisiones son independientes por departamento. La espera de un equipo no bloquea a los demás.
          </p>
        )}
        {ticket.arbitrations.length > 0 && (
          <section className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h4 className="font-semibold text-amber-900">Historial de arbitraje</h4>
            <ul className="mt-2 space-y-2 text-sm text-amber-900">
              {ticket.arbitrations.map((item) => (
                <li key={`${item.trigger_id}-${item.created_at}`}>
                  <strong>{item.trigger_id}</strong> · árbitro: {item.arbitrator} ·{' '}
                  {item.result}. {item.rule}
                </li>
              ))}
            </ul>
          </section>
        )}
        {ticket.status === 'terminado' && ticket.final_document && (
          <button
            type="button"
            onClick={onDownload}
            disabled={busy}
            className="mt-4 rounded-full bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50"
          >
            Descargar documento final (JSON)
          </button>
        )}
        <div className="mt-4 space-y-4">
          {ticket.sections.length === 0 ? (
            <p className="rounded-lg bg-amber-50 p-4 text-sm text-amber-900">
              No se activó ningún departamento. Ventas debe aclarar qué servicio solicita el cliente.
            </p>
          ) : (
            ticket.sections.map((section) => {
              const workstream = ticket.handoff?.active_workstreams.find(
                (item) => item.department_id === section.department_id,
              );
              return (
                <article
                  key={section.department_id}
                  className="rounded-lg border border-slate-200 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-bold capitalize text-slate-900">
                      {section.department_id}
                    </h4>
                    <span className="text-sm text-slate-600">
                      {ticket.status === 'analisis_completo'
                        ? `Responsable: ${workstream?.contact ?? APPROVER_NAMES[section.department_id] ?? 'No asignado'}`
                        : `Responsable: ${APPROVER_NAMES[section.department_id] ?? 'No asignado'} · Decisión por admin`}
                    </span>
                  </div>
                  {ticket.status !== 'analisis_completo' && section.draft_content && (
                    <div className="mt-3 rounded-lg bg-slate-50 p-4">
                      <h5 className="text-sm font-semibold text-slate-800">Borrador vigente</h5>
                      <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                        {section.draft_content}
                      </p>
                      <p className="mt-2 text-xs text-slate-500">
                        Versión {section.evaluation_results?.iteration_count ?? '—'} ·{' '}
                        {section.evaluation_results?.section_status ?? 'estado no disponible'}
                      </p>
                      {section.evaluation_results?.result && (
                        <div className="mt-3 border-t border-slate-200 pt-3 text-sm">
                          <p className="font-semibold text-slate-800">
                            Evaluación automática:{' '}
                            {section.evaluation_results.result.overall_pass
                              ? 'aprobada'
                              : 'requiere revisión'}
                          </p>
                          <p className="mt-1 text-slate-600">
                            Legibilidad:{' '}
                            {section.evaluation_results.result.readability?.details ?? 'sin detalle'}
                          </p>
                          {(section.evaluation_results.result.relevance?.missing_aspects?.length ?? 0) > 0 && (
                            <p className="mt-1 text-amber-800">
                              Aspectos omitidos:{' '}
                              {section.evaluation_results.result.relevance?.missing_aspects?.join('; ')}
                            </p>
                          )}
                          {(section.evaluation_results.result.compliance?.violations?.length ?? 0) > 0 && (
                            <ul className="mt-1 list-disc pl-5 text-amber-800">
                              {section.evaluation_results.result.compliance?.violations?.map((violation) => (
                                <li key={violation}>{violation}</li>
                              ))}
                            </ul>
                          )}
                          <p className="mt-1 text-slate-600">
                            {section.evaluation_results.result.feedback_for_generator}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                  {ticket.status === 'analisis_completo' && section.key_aspects.length > 0 ? (
                    <ul className="mt-3 space-y-3">
                      {section.key_aspects.map((aspect, index) => (
                        <li key={`${aspect.aspect}-${index}`} className="text-sm text-slate-700">
                          <p className="font-semibold">{aspect.aspect}</p>
                          <p>{display(aspect.value)}</p>
                          {aspect.evidence && (
                            <p className="mt-1 text-xs text-slate-500">
                              Evidencia: {aspect.evidence}
                            </p>
                          )}
                          {aspect.open_question && (
                            <p className="mt-1 text-xs font-medium text-amber-800">
                              Pendiente: {aspect.open_question}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : ticket.status === 'analisis_completo' ? (
                    <p className="mt-3 text-sm text-slate-600">
                      No hay aspectos concretos; revisar las preguntas abiertas.
                    </p>
                  ) : (
                    <div className="mt-3 text-sm text-slate-600">
                      <p>
                        Estado de aprobación:{' '}
                        {ticket.approval_branches.find(
                          (branch) => branch.department_id === section.department_id,
                        )?.status ?? section.approval_status}
                      </p>
                      {ticket.approval_decisions
                        .filter((decision) => decision.department_id === section.department_id)
                        .slice(-1)
                        .map((decision) => (
                          <p key={decision.created_at} className="mt-1">
                            Última decisión: {decision.action} · {decision.approver_email}
                            {decision.comment ? ` · ${decision.comment}` : ''}
                          </p>
                        ))}
                    </div>
                  )}
                  {ticket.status === 'esperando_aprobación' &&
                    ticket.can_approve &&
                    ticket.approval_branches.find(
                      (branch) => branch.department_id === section.department_id,
                    )?.status === 'pending' && (
                      <div className="mt-4 space-y-3 border-t border-slate-200 pt-4">
                        <label className="block text-sm font-medium text-slate-700">
                          Comentario (obligatorio para rechazo o solicitud de cambios)
                          <textarea
                            value={comments[section.department_id] ?? ''}
                            onChange={(event) =>
                              onCommentChange(section.department_id, event.target.value)
                            }
                            rows={3}
                            className="mt-1 block w-full rounded-lg border border-slate-300 p-2 text-sm"
                          />
                        </label>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => onDecision(section.department_id, 'approve')}
                            disabled={busy}
                            className="rounded-full bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                          >
                            Aprobar
                          </button>
                          <button
                            type="button"
                            onClick={() => onDecision(section.department_id, 'request_changes')}
                            disabled={busy || !(comments[section.department_id] ?? '').trim()}
                            className="rounded-full bg-amber-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                          >
                            Solicitar cambios
                          </button>
                          <button
                            type="button"
                            onClick={() => onDecision(section.department_id, 'reject')}
                            disabled={busy || !(comments[section.department_id] ?? '').trim()}
                            className="rounded-full bg-red-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                          >
                            Rechazar
                          </button>
                        </div>
                      </div>
                    )}
                  {ticket.status === 'needs_human_review' &&
                    ticket.can_approve &&
                    ticket.approval_branches.find(
                      (branch) => branch.department_id === section.department_id,
                    )?.status === 'revision_requested' && (
                      <button
                        type="button"
                        onClick={() => onResumeApproval(section.department_id)}
                        disabled={busy}
                        className="mt-4 rounded-full bg-amber-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
                      >
                        {busy ? 'Reanudando...' : 'Reanudar revisión de sección'}
                      </button>
                    )}
                </article>
              );
            })
          )}
        </div>
        {ticket.handoff && (
          <div className="mt-5 rounded-lg bg-brand/5 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-brand">
              Handoff Parte 2 · versión {ticket.handoff.schema_version}
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">
              {ticket.handoff.summary}
            </p>
          </div>
        )}
      </section>
    </>
  );
}

export default function RfpIntakeClient() {
  const [tickets, setTickets] = useState<RfpTicketSummary[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [ticket, setTicket] = useState<RfpTicketDetail | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [comments, setComments] = useState<Record<string, string>>({});
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    void listRfpTickets()
      .then((items) => {
        if (!active) return;
        setTickets(items);
        const nextSelected = items[0]?.ticket_id ?? null;
        setSelectedTicketId(nextSelected);
        if (!nextSelected) {
          setTicket(null);
        }
      })
      .catch((requestError: unknown) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : 'No se pudieron cargar los tickets.',
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedTicketId) {
      return;
    }

    let active = true;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const detail = await getRfpTicket(selectedTicketId);
        if (!active) return;
        setTicket(detail);
        setTickets((current) =>
          current.map((item) => (item.ticket_id === detail.ticket_id ? detail : item)),
        );
        if (
          (detail.processing && !detail.processing_error) ||
          detail.status === 'esperando_aprobación'
        ) {
          timeout = setTimeout(
            () => void poll(),
            detail.processing ? 3000 : 15000,
          );
        }
      } catch (requestError: unknown) {
        if (!active) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : 'No se pudo consultar el ticket.',
        );
        timeout = setTimeout(() => void poll(), 5000);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timeout) clearTimeout(timeout);
    };
  }, [selectedTicketId]);

  const handleUpload = async () => {
    if (!file) return;
    setError('');
    setUploading(true);
    try {
      const created = await uploadRfp(file);
      setTickets((current) => [created, ...current]);
      setSelectedTicketId(created.ticket_id);
      setTicket(null);
      setFile(null);
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error ? requestError.message : 'No se pudo cargar el PDF.',
      );
    } finally {
      setUploading(false);
    }
  };

  const handleRetry = async () => {
    if (!selectedTicketId) return;
    setError('');
    setRetrying(true);
    try {
      await retryRfpTicket(selectedTicketId);
      setTicket(await getRfpTicket(selectedTicketId));
      setTickets((current) =>
        current.map((item) =>
          item.ticket_id === selectedTicketId
            ? {
                ...item,
                status: 'analizando',
                processing: true,
                retry_available: false,
                processing_error: null,
              }
            : item,
        ),
      );
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'No se pudo reintentar el análisis.',
      );
    } finally {
      setRetrying(false);
    }
  };

  const refreshSelectedTicket = async () => {
    if (!selectedTicketId) return;
    const refreshed = await getRfpTicket(selectedTicketId);
    setTicket(refreshed);
    setTickets((current) =>
      current.map((item) => (item.ticket_id === refreshed.ticket_id ? refreshed : item)),
    );
  };

  const runWorkflowAction = async (action: () => Promise<unknown>) => {
    setError('');
    setWorkflowBusy(true);
    try {
      await action();
      await refreshSelectedTicket();
    } catch (requestError: unknown) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : 'No se pudo completar la acción del flujo RFP.',
      );
    } finally {
      setWorkflowBusy(false);
    }
  };

  const handleDecision = async (
    departmentId: string,
    action: RfpApprovalAction,
  ) => {
    if (!selectedTicketId || !ticket) return;
    const section = ticket.sections.find(
      (item) => item.department_id === departmentId,
    );
    const evaluation = section?.evaluation_results;
    const digest = evaluation?.result?.draft_sha256;
    const version = evaluation?.iteration_count;
    if (!digest || !version) {
      setError('La sección no tiene una versión de borrador aprobable.');
      return;
    }
    const comment = comments[departmentId]?.trim();
    await runWorkflowAction(async () => {
      await decideRfpApproval(selectedTicketId, departmentId, {
        action,
        draft_sha256: digest,
        draft_version: version,
        ...(comment ? { comment } : {}),
      });
      setComments((current) => ({ ...current, [departmentId]: '' }));
    });
  };

  const handleResumeApproval = (departmentId: string) => {
    if (!selectedTicketId) return;
    void runWorkflowAction(() =>
      resumeRfpApprovalRevision(selectedTicketId, departmentId),
    );
  };

  const handleDownload = async () => {
    if (!selectedTicketId) return;
    await runWorkflowAction(async () => {
      const blob = await downloadFinalRfpDocument(selectedTicketId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `rfp-${selectedTicketId}-final.json`;
      link.click();
      URL.revokeObjectURL(url);
    });
  };

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Recibir una RFP</h2>
        <p className="mt-1 text-sm text-slate-600">
          Carga un PDF de hasta 20 MB. El ticket se crea de inmediato y el análisis continúa en segundo plano.
        </p>
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label htmlFor="rfp-pdf" className="mb-1 block text-sm font-semibold text-slate-700">
              Documento PDF
            </label>
            <input
              id="rfp-pdf"
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-lg border border-slate-300 bg-white p-2 text-sm text-slate-700"
            />
            <p className="mt-1 text-xs text-slate-500">
              Solo PDF · máximo 20 MB
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleUpload()}
            disabled={
              uploading ||
              !file ||
              file.size > MAX_UPLOAD_BYTES ||
              (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf'))
            }
            className="rounded-full bg-brand px-5 py-2.5 text-sm font-bold text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? 'Cargando...' : 'Crear ticket'}
          </button>
        </div>
        {file && file.size > MAX_UPLOAD_BYTES && (
          <p className="mt-2 text-sm text-red-700">El PDF supera el límite de 20 MB.</p>
        )}
      </section>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(240px,0.8fr)_minmax(0,2fr)]">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-bold text-slate-900">Mis tickets</h2>
            {loading && <span className="text-xs text-slate-500">Cargando...</span>}
          </div>
          {tickets.length === 0 && !loading ? (
            <p className="mt-4 text-sm text-slate-600">Aún no hay documentos recibidos.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {tickets.map((item) => (
                <li key={item.ticket_id}>
                  <button
                    type="button"
                    onClick={() => setSelectedTicketId(item.ticket_id)}
                    aria-current={selectedTicketId === item.ticket_id ? 'true' : undefined}
                    className={`w-full rounded-lg border p-3 text-left transition ${
                      selectedTicketId === item.ticket_id
                        ? 'border-brand bg-brand/5'
                        : 'border-slate-200 hover:border-brand/40'
                    }`}
                  >
                    <span className="block truncate font-mono text-xs text-slate-500">
                      {item.ticket_id}
                    </span>
                    <span className="mt-1 block text-sm font-semibold text-slate-800">
                      {STATUS_LABELS[item.status]}
                    </span>
                    <span className="mt-1 block text-xs text-slate-500">
                      {new Date(item.created_at).toLocaleString('es-ES')}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="min-w-0 space-y-5">
          {ticket ? (
            <>
              <header className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wide text-brand">
                  Ticket {ticket.ticket_id}
                </p>
                <h2 className="mt-2 text-xl font-extrabold text-slate-900">
                  {STATUS_LABELS[ticket.status]}
                </h2>
                {ticket.status === 'analizando' && !ticket.processing_error && (
                  <p className="mt-2 text-sm text-slate-600" role="status">
                    PDF recibido. Se está convirtiendo y analizando; el estado se actualizará automáticamente.
                  </p>
                )}
                {ticket.processing_error && (
                  <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3">
                    <p className="text-sm text-red-800">{ticket.processing_error}</p>
                    {ticket.retry_available && (
                      <button
                        type="button"
                        onClick={() => void handleRetry()}
                        disabled={retrying}
                        className="mt-3 rounded-full bg-red-700 px-4 py-2 text-sm font-bold text-white hover:bg-red-800 disabled:opacity-50"
                      >
                        {retrying ? 'Reintentando...' : 'Reintentar análisis'}
                      </button>
                    )}
                  </div>
                )}
              </header>
              <TicketResult
                ticket={ticket}
                busy={workflowBusy}
                comments={comments}
                onGenerate={() =>
                  void runWorkflowAction(() =>
                    generateRfpResponses(ticket.ticket_id),
                  )
                }
                onStartApprovals={() =>
                  void runWorkflowAction(() =>
                    startRfpApprovals(ticket.ticket_id),
                  )
                }
                onResumeApproval={handleResumeApproval}
                onCommentChange={(departmentId, value) =>
                  setComments((current) => ({
                    ...current,
                    [departmentId]: value,
                  }))
                }
                onDecision={(departmentId, action) =>
                  void handleDecision(departmentId, action)
                }
                onDownload={() => void handleDownload()}
              />
            </>
          ) : selectedTicketId ? (
            <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600">
              Consultando estado del ticket...
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">
              Selecciona un ticket o carga una RFP para ver el análisis.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
