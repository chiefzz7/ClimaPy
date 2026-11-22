import {
  Bell,
  BellOff,
  CheckCircle2,
  Loader2,
  Pause,
  Play,
  Plus,
  Send,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createReminder,
  deleteReminder,
  fetchVapidPublicKey,
  getReminder,
  sendTestReminder,
  updateReminder,
} from "../services/api";
import {
  detectPushCapabilities,
  getExistingPushSubscription,
  subscribeToWebPush,
} from "../services/push";
import {
  loadReminderRefs,
  removeReminderRef,
  updateCachedReminder,
  upsertReminderRef,
} from "../services/storage";
import type {
  ForecastWindow,
  PushSubscriptionPayload,
  SavedLocation,
  ScheduleType,
  StoredReminderRef,
} from "../types/weather";

interface RemindersSectionProps {
  activeLocation: SavedLocation;
}

const WEEKDAY_BUTTONS = [
  { value: 0, label: "Seg" },
  { value: 1, label: "Ter" },
  { value: 2, label: "Qua" },
  { value: 3, label: "Qui" },
  { value: 4, label: "Sex" },
  { value: 5, label: "Sáb" },
  { value: 6, label: "Dom" },
];

const WINDOW_LABELS: Record<ForecastWindow, string> = {
  today: "Previsão de hoje",
  tomorrow: "Previsão de amanhã",
  next_3_days: "Próximos 3 dias",
};

function todayIsoLocal(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function RemindersSection({ activeLocation }: RemindersSectionProps) {
  const [refs, setRefs] = useState<StoredReminderRef[]>(() => loadReminderRefs());
  const [vapidConfigured, setVapidConfigured] = useState<boolean | null>(null);
  const [vapidPublicKey, setVapidPublicKey] = useState<string | null>(null);
  const [pushSub, setPushSub] = useState<PushSubscriptionPayload | null>(null);
  const [syncing, setSyncing] = useState(false);

  const [label, setLabel] = useState("Resumo do clima");
  const [scheduleType, setScheduleType] = useState<ScheduleType>("daily");
  const [timeOfDay, setTimeOfDay] = useState("07:30");
  const [daysOfWeek, setDaysOfWeek] = useState<number[]>([0, 1, 2, 3, 4]);
  const [onceDate, setOnceDate] = useState<string>(todayIsoLocal);
  const [forecastWindow, setForecastWindow] = useState<ForecastWindow>("today");
  const [rainFilterEnabled, setRainFilterEnabled] = useState(false);
  const [minRainProb, setMinRainProb] = useState(50);

  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const capabilities = detectPushCapabilities();

  const syncWithServer = useCallback(async () => {
    setSyncing(true);
    try {
      const vapid = await fetchVapidPublicKey();
      setVapidConfigured(vapid.configured);
      setVapidPublicKey(vapid.public_key);

      const existingSub = await getExistingPushSubscription();
      setPushSub(existingSub);

      const currentRefs = loadReminderRefs();
      const refreshed: StoredReminderRef[] = [];
      for (const ref of currentRefs) {
        try {
          const remote = await getReminder(ref.id, ref.token);
          refreshed.push({ id: ref.id, token: ref.token, cached: remote });
          updateCachedReminder(remote);
        } catch (err) {
          if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
            removeReminderRef(ref.id);
          } else {
            refreshed.push(ref);
          }
        }
      }
      setRefs(refreshed);
    } catch {
      setVapidConfigured(false);
    } finally {
      setSyncing(false);
    }
  }, []);

  useEffect(() => {
    void syncWithServer();
  }, [syncWithServer]);

  async function handleEnablePush(): Promise<PushSubscriptionPayload | null> {
    if (!vapidConfigured || !vapidPublicKey) {
      setFeedback({
        kind: "err",
        text: "Gere as chaves locais no .env do servidor (generate_keys.py --write) para ativar Web Push.",
      });
      return null;
    }
    try {
      const sub = await subscribeToWebPush(vapidPublicKey);
      setPushSub(sub);
      setFeedback({
        kind: "ok",
        text: "Notificações Web Push ativadas neste dispositivo!",
      });
      return sub;
    } catch (err) {
      setFeedback({
        kind: "err",
        text: err instanceof Error ? err.message : "Não foi possível ativar notificações.",
      });
      return null;
    }
  }

  function toggleWeekday(day: number) {
    setDaysOfWeek((prev) =>
      prev.includes(day) ? prev.filter((item) => item !== day) : [...prev, day].sort()
    );
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFeedback(null);

    if (scheduleType === "weekly" && daysOfWeek.length === 0) {
      setFeedback({ kind: "err", text: "Selecione ao menos um dia da semana." });
      return;
    }

    setSubmitting(true);
    try {
      let activeSub = pushSub;
      if (!activeSub) {
        activeSub = await handleEnablePush();
      }
      if (!activeSub) {
        return;
      }

      const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Sao_Paulo";
      const targetTz =
        activeLocation.timezone && activeLocation.timezone !== "auto"
          ? activeLocation.timezone
          : browserTz;

      const created = await createReminder({
        label: label.trim() || "Alerta climático",
        location_name: activeLocation.displayName,
        latitude: activeLocation.latitude,
        longitude: activeLocation.longitude,
        timezone: targetTz,
        schedule_type: scheduleType,
        time_of_day: timeOfDay,
        days_of_week: scheduleType === "weekly" ? daysOfWeek : [],
        once_date: scheduleType === "once" ? onceDate : null,
        forecast_window: forecastWindow,
        min_rain_probability: rainFilterEnabled ? minRainProb : null,
        subscription: activeSub,
      });

      const nextRefs = upsertReminderRef({
        id: created.reminder.id,
        token: created.reminder_token,
        cached: created.reminder,
      });
      setRefs(nextRefs);
      setFeedback({
        kind: "ok",
        text: `Lembrete "${created.reminder.label}" salvo com segurança neste aparelho!`,
      });
    } catch (err) {
      setFeedback({
        kind: "err",
        text: err instanceof ApiError ? err.detail : "Erro ao salvar lembrete.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleEnabled(ref: StoredReminderRef) {
    if (!ref.cached) return;
    setBusyId(ref.id);
    setFeedback(null);
    try {
      const updated = await updateReminder(ref.id, ref.token, {
        enabled: !ref.cached.enabled,
      });
      setRefs(updateCachedReminder(updated));
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
        setRefs(removeReminderRef(ref.id));
      }
      setFeedback({
        kind: "err",
        text: err instanceof ApiError ? err.detail : "Não foi possível atualizar o lembrete.",
      });
    } finally {
      setBusyId(null);
    }
  }

  async function handleTestPush(ref: StoredReminderRef) {
    setBusyId(ref.id);
    setFeedback(null);
    try {
      const res = await sendTestReminder(ref.id, ref.token);
      setFeedback({
        kind: "ok",
        text: `Teste enviado: ${res.title} — ${res.body}`,
      });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
        setRefs(removeReminderRef(ref.id));
      }
      setFeedback({
        kind: "err",
        text: err instanceof ApiError ? err.detail : "Falha ao disparar notificação de teste.",
      });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(ref: StoredReminderRef) {
    setBusyId(ref.id);
    setFeedback(null);
    try {
      await deleteReminder(ref.id, ref.token);
      setRefs(removeReminderRef(ref.id));
      setFeedback({ kind: "ok", text: "Lembrete removido definitivamente." });
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 410)) {
        setRefs(removeReminderRef(ref.id));
      } else {
        setFeedback({
          kind: "err",
          text: err instanceof ApiError ? err.detail : "Erro ao remover lembrete.",
        });
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section aria-label="Lembretes e notificações" className="space-y-4">
      <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 text-xs text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <div>
          <p className="font-bold">Privacidade garantida • Zero Login</p>
          <p className="mt-0.5 leading-relaxed opacity-90">
            Nenhum e-mail, senha ou dado pessoal é coletado. O controle de cada lembrete fica
            protegido por um token exclusivo deste dispositivo e pela inscrição cifrada com Fernet.
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            {pushSub ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            ) : (
              <Bell className="h-5 w-5 text-sky-500" />
            )}
            <div>
              <p className="text-sm font-bold text-slate-900 dark:text-slate-100">
                Status das Notificações Web Push
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {pushSub
                  ? "Ativo neste navegador — pronto para receber alertas no horário escolhido."
                  : capabilities.isIosBrowserNeedingInstall
                    ? "No iPhone/iPad: adicione à Tela de Início pelo menu Compartilhar para ativar Push."
                    : capabilities.supported
                      ? "Clique em Ativar para autorizar notificações deste aparelho."
                      : "Web Push indisponível neste navegador (nos apps Android/iOS nativos usaremos notificações locais)."}
              </p>
            </div>
          </div>

          {!pushSub && capabilities.supported && (
            <button
              type="button"
              onClick={() => void handleEnablePush()}
              className="rounded-xl bg-sky-600 px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-sky-700"
            >
              Ativar Notificações
            </button>
          )}
        </div>
      </div>

      {feedback && (
        <div
          role="status"
          className={`rounded-2xl border px-4 py-3 text-xs font-medium ${
            feedback.kind === "ok"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-200"
              : "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/40 dark:text-rose-200"
          }`}
        >
          {feedback.text}
        </div>
      )}

      <form
        onSubmit={(e) => void handleCreate(e)}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-base font-bold text-slate-900 dark:text-slate-100">
            <Plus className="h-4 w-4 text-sky-500" />
            Novo Lembrete para {activeLocation.name}
          </h3>
          <span className="text-xs text-slate-400">
            {activeLocation.latitude.toFixed(2)}, {activeLocation.longitude.toFixed(2)}
          </span>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>Nome do lembrete</span>
            <input
              type="text"
              required
              minLength={2}
              maxLength={80}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>Horário da notificação</span>
            <input
              type="time"
              required
              value={timeOfDay}
              onChange={(e) => setTimeOfDay(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>Frequência</span>
            <select
              value={scheduleType}
              onChange={(e) => setScheduleType(e.target.value as ScheduleType)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="daily">Todos os dias</option>
              <option value="weekly">Dias específicos da semana</option>
              <option value="once">Data específica (uma vez)</option>
            </select>
          </label>

          <label className="space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>Janela da previsão no aviso</span>
            <select
              value={forecastWindow}
              onChange={(e) => setForecastWindow(e.target.value as ForecastWindow)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            >
              <option value="today">Previsão de hoje</option>
              <option value="tomorrow">Previsão de amanhã</option>
              <option value="next_3_days">Resumo dos próximos 3 dias</option>
            </select>
          </label>
        </div>

        {scheduleType === "weekly" && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-slate-600 dark:text-slate-300">
              Dias da semana
            </p>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAY_BUTTONS.map((day) => {
                const selected = daysOfWeek.includes(day.value);
                return (
                  <button
                    key={day.value}
                    type="button"
                    onClick={() => toggleWeekday(day.value)}
                    className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition ${
                      selected
                        ? "bg-sky-600 text-white"
                        : "border border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                    }`}
                  >
                    {day.label}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {scheduleType === "once" && (
          <label className="block max-w-xs space-y-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            <span>Data do lembrete</span>
            <input
              type="date"
              required
              value={onceDate}
              min={todayIsoLocal()}
              onChange={(e) => setOnceDate(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-sky-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            />
          </label>
        )}

        <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 p-3 text-xs dark:bg-slate-800/60">
          <label className="inline-flex cursor-pointer items-center gap-2 font-medium text-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              checked={rainFilterEnabled}
              onChange={(e) => setRainFilterEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            Avisar somente se a chance de chuva for maior ou igual a:
          </label>
          {rainFilterEnabled && (
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={10}
                max={100}
                step={5}
                value={minRainProb}
                onChange={(e) => setMinRainProb(Number(e.target.value))}
                className="accent-sky-600"
              />
              <span className="w-10 font-bold text-sky-600 dark:text-sky-400">
                {minRainProb}%
              </span>
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting || !capabilities.supported || vapidConfigured === false}
          className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
          <span>{submitting ? "Salvando lembrete..." : "Salvar Lembrete"}</span>
        </button>
      </form>

      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">
            Meus Lembretes neste Dispositivo ({refs.length})
          </h4>
          {syncing && <Loader2 className="h-4 w-4 animate-spin text-sky-500" />}
        </div>

        {refs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
            <BellOff className="mx-auto mb-2 h-6 w-6 text-slate-400" />
            Você ainda não cadastrou lembretes neste navegador.
          </div>
        ) : (
          refs.map((ref) => {
            const rem = ref.cached;
            const isBusy = busyId === ref.id;
            return (
              <div
                key={ref.id}
                className="flex flex-col justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      {rem?.label ?? "Lembrete salvo"}
                    </span>
                    {rem && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                          rem.enabled
                            ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                            : "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
                        }`}
                      >
                        {rem.enabled ? "Ativo" : "Pausado"}
                      </span>
                    )}
                  </div>
                  {rem && (
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {rem.location_name} • <strong>{rem.time_of_day}</strong> •{" "}
                      {WINDOW_LABELS[rem.forecast_window]}
                      {rem.min_rain_probability !== null
                        ? ` • Chuva ≥ ${rem.min_rain_probability}%`
                        : ""}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void handleTestPush(ref)}
                    className="inline-flex items-center gap-1 rounded-xl border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-50 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-300"
                  >
                    <Send className="h-3.5 w-3.5" />
                    Testar
                  </button>

                  {rem && (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => void handleToggleEnabled(ref)}
                      className="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {rem.enabled ? (
                        <>
                          <Pause className="h-3.5 w-3.5" />
                          Pausar
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5" />
                          Ativar
                        </>
                      )}
                    </button>
                  )}

                  <button
                    type="button"
                    disabled={isBusy}
                    onClick={() => void handleDelete(ref)}
                    aria-label="Excluir lembrete"
                    className="inline-flex items-center gap-1 rounded-xl border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-50 dark:border-rose-900/50 dark:text-rose-400 dark:hover:bg-rose-950/40"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Excluir
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
