import type { PushSubscriptionPayload } from "../types/weather";
import { urlBase64ToUint8Array } from "../utils/format";

export interface PushCapabilities {
  supported: boolean;
  permission: NotificationPermission | "unsupported";
  isIosBrowserNeedingInstall: boolean;
}

export function detectPushCapabilities(): PushCapabilities {
  const hasSw = typeof navigator !== "undefined" && "serviceWorker" in navigator;
  const hasPush = typeof window !== "undefined" && "PushManager" in window;
  const hasNotification = typeof Notification !== "undefined";

  const ua = typeof navigator !== "undefined" ? navigator.userAgent.toLowerCase() : "";
  const isIos = /iphone|ipad|ipod/.test(ua);
  const isStandalone =
    (typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(display-mode: standalone)").matches) ||
    Boolean((navigator as { standalone?: boolean } | undefined)?.standalone);

  return {
    supported: hasSw && hasPush && hasNotification,
    permission: hasNotification ? Notification.permission : "unsupported",
    isIosBrowserNeedingInstall: isIos && !isStandalone,
  };
}

export async function registerAppServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }
  try {
    return await navigator.serviceWorker.register("/sw.js", { scope: "/" });
  } catch {
    return null;
  }
}

function serializeSubscription(sub: PushSubscription): PushSubscriptionPayload {
  const json = sub.toJSON();
  const p256dh = json.keys?.p256dh ?? "";
  const auth = json.keys?.auth ?? "";
  if (!sub.endpoint || !p256dh || !auth) {
    throw new Error("Inscrição Web Push retornada pelo navegador está incompleta.");
  }
  return {
    endpoint: sub.endpoint,
    keys: { p256dh, auth },
  };
}

export async function getExistingPushSubscription(): Promise<PushSubscriptionPayload | null> {
  const capabilities = detectPushCapabilities();
  if (!capabilities.supported) {
    return null;
  }
  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  return existing ? serializeSubscription(existing) : null;
}

export async function subscribeToWebPush(
  vapidPublicKey: string
): Promise<PushSubscriptionPayload> {
  const capabilities = detectPushCapabilities();
  if (!capabilities.supported) {
    if (capabilities.isIosBrowserNeedingInstall) {
      throw new Error(
        "No iPhone/iPad, toque em Compartilhar > 'Adicionar à Tela de Início' e abra o app instalado para ativar notificações."
      );
    }
    throw new Error("Este navegador não suporta notificações Web Push.");
  }

  let permission = Notification.permission;
  if (permission === "default") {
    permission = await Notification.requestPermission();
  }
  if (permission !== "granted") {
    throw new Error(
      "Permissão de notificações bloqueada. Libere as notificações nas configurações do navegador."
    );
  }

  const registration =
    (await registerAppServiceWorker()) ?? (await navigator.serviceWorker.ready);
  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    return serializeSubscription(existing);
  }

  const created = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
  });
  return serializeSubscription(created);
}
