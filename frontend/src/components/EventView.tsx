"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime } from "@/lib/format";
import { MODE_LABEL, mapsUrl, placeText } from "@/lib/places";
import { Pic } from "./Pic";
import { useToast } from "@/lib/toast";
import { FormRenderer } from "./FormRenderer";
import { Reviews } from "./Reviews";
import { Button, Empty, Stars, Tag } from "./ui";

export function EventView({ slug, initial }: { slug: string; initial: any }) {
  const { user, loading } = useAuth();
  const toast = useToast();
  const [e, setE] = useState<any>(initial);
  const [missing, setMissing] = useState(false);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const load = () => api(`/events/${slug}`).then(setE).catch(() => !initial && setMissing(true));
  useEffect(() => { load(); }, [slug, user?.id]);

  if (missing) return <div className="wrap py-32"><Empty title="Event not found" body="It may be private, or the address is wrong." action={<Button href="/discover">Browse events</Button>} /></div>;
  if (!e) return <div className="wrap py-32 muted caret">Loading</div>;
  const reg = e.my_registration;
  const closes = new Date(e.registration_closes_at || e.starts_at);
  const closed = Date.now() >= closes.getTime() || e.status === "cancelled" || e.phase === "past";
  const full = e.capacity && e.registered >= e.capacity;

  const register = async () => {
    setBusy(true); setErrors({});
    try { await api(`/events/${slug}/register`, { method: "POST", body: { answers } }); toast("You're registered. Check your email for the confirmation."); await load(); }
    catch (x: any) {
      if (x instanceof ApiError && x.detail?.errors) setErrors(x.detail.errors);
      toast(x.message, "err");
    } finally { setBusy(false); }
  };
  const cancel = async () => { if (!confirm("Cancel your registration?")) return; try { await api(`/events/${slug}/register`, { method: "DELETE" }); toast("Registration cancelled"); await load(); } catch (x: any) { toast(x.message, "err"); } };

  return (
    <div className="wrap py-16">
      <div className="grid grid-cols-1 gap-14 lg:grid-cols-[1.3fr_.7fr]">
        <div>
          <Link href={`/c/${e.club.slug}`} className="link muted">{e.club.name}</Link>
          <h1 className="display h-xl mt-3">{e.title}</h1>
          <div className="mt-6 flex flex-wrap gap-3 items-center">
            <Tag>{fmtDateTime(e.starts_at)}</Tag>{e.venue && <Tag>{e.venue}</Tag>}<Tag>{MODE_LABEL[e.location?.mode || "onsite"]}</Tag>
            {e.phase === "ongoing" && <span className="tag" style={{ color: "var(--ok)", borderColor: "var(--ok)" }}>● Happening now</span>}{e.phase === "past" && e.status !== "cancelled" && <Tag>Ended</Tag>}
            {e.status === "cancelled" && <Tag>Cancelled</Tag>}
            {e.rating?.count > 0 && <span className="flex items-center gap-2"><Stars value={e.rating.average} size={15} /><span className="muted text-sm">{e.rating.average} ({e.rating.count})</span></span>}
          </div>
          {e.banner_url && <Pic src={e.banner_url} className="mt-10 w-full max-h-[420px] object-cover border border-line" style={{ borderRadius: "var(--r)" }} />}
          {e.description && <div className="mt-10 max-w-[65ch] whitespace-pre-line text-[1.05rem]">{e.description}</div>}
          {(() => {
            const loc = e.location || {}, online = loc.mode !== "onsite", physical = loc.mode !== "online";
            const map = physical ? mapsUrl(loc) : null;
            return (
              <div className="mt-10 panel p-6 max-w-xl space-y-3">
                <p className="display h-md">Where</p>
                {physical && <p>{[e.venue, placeText(loc.address, loc.place_name)].filter(Boolean).join(", ") || "Location to be announced"}{map && <> · <a className="link" href={map} target="_blank" rel="noopener noreferrer">Open in maps</a></>}</p>}
                {online && (e.online_url
                  ? <p><a className="btn btn-primary btn-sm" href={e.online_url} target="_blank" rel="noopener noreferrer">Join online</a></p>
                  : <p className="muted text-sm">The online link is shared with registered attendees.</p>)}
              </div>
            );
          })()}
        </div>

        <aside className="lg:sticky lg:top-24 self-start">
          {reg ? (
            <div className="ticket" style={{ ["--cut" as any]: "58%" }}>
              <div className="p-6" style={{ minHeight: 190 }}>
                <p className="muted text-sm">{reg.status === "waitlisted" ? "Waitlisted" : reg.checked_in_at ? "Checked in" : "Your ticket"}</p>
                <p className="display h-md mt-2">{e.title}</p>
                <p className="text-sm mt-3 font-mono" style={{ fontFamily: "var(--font-body)" }}>{reg.ticket_code}</p>
              </div>
              <div className="perf" />
              <div className="stub px-6 pb-6">
                {reg.status === "confirmed"
                  ? <img src={`/api/registrations/${reg.id}/qr.svg`} alt={`QR ticket ${reg.ticket_code}`} className="mx-auto w-44 h-44 p-2" style={{ background: "#fff", borderRadius: 4 }} />
                  : <p className="muted text-sm py-6">You&apos;ll get an email and a ticket if a seat opens up.</p>}
                {!reg.checked_in_at && <button className="link muted text-sm mt-4 block mx-auto" onClick={cancel}>Cancel registration</button>}
              </div>
            </div>
          ) : (
            <div className="panel p-6">
              <p className="display h-md">Register</p>
              <p className="muted text-sm mt-1">{e.capacity ? `${e.registered} of ${e.capacity} seats taken` : `${e.registered} going`}</p>
              {closed ? <p className="mt-6">{e.status === "cancelled" ? "This event was cancelled." : e.phase === "past" ? "This event has ended." : "Registration is closed."}</p>
                : loading ? null : !user ? <div className="mt-6"><Button href={`/login?next=/e/${slug}`} variant="primary">Sign in to register</Button></div>
                : <div className="mt-6">
                    {full && <p className="muted text-sm mb-4">This event is full. {" "}If the organizers offer a waitlist you&apos;ll be added.</p>}
                    <FormRenderer fields={e.registration_fields || []} value={answers} onChange={setAnswers} errors={errors} />
                    <Button className="mt-7 w-full" variant="primary" loading={busy} onClick={register}>{full ? "Try the waitlist" : "Register"}</Button>
                  </div>}
            </div>
          )}
        </aside>
      </div>
      <div className="mt-28"><Reviews kind="events" slug={slug} /></div>
    </div>
  );
}
