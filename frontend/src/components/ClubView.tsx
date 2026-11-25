"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { FONT_MAP, fgOn } from "@/lib/color";
import { fmtDate } from "@/lib/format";
import { locationLine, mapsUrl } from "@/lib/places";
import { useTheme } from "@/lib/theme";
import { useToast } from "@/lib/toast";
import { AttachmentList } from "./Attachments";
import { TicketCard } from "./Cards";
import { FormRenderer } from "./FormRenderer";
import { Pic } from "./Pic";
import { Reviews } from "./Reviews";
import { Button, Empty, Seal, Stars, Tag } from "./ui";

function Section({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return <section><div className="flex items-end justify-between flex-wrap gap-4"><h2 className="display h-lg">{title}</h2>{aside}</div><div className="mt-10">{children}</div></section>;
}
const Grid = ({ events }: { events: any[] }) => <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">{events.map((e) => <TicketCard key={e.slug} e={e} />)}</div>;

export function ClubView({ slug, initial }: { slug: string; initial: any }) {
  const { user } = useAuth();
  const { mode } = useTheme();
  const toast = useToast();
  const [data, setData] = useState<any>(initial);
  const [missing, setMissing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [answers, setAnswers] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);

  const load = () => api(`/public/clubs/${slug}`).then(setData).catch(() => !initial && setMissing(true));
  useEffect(() => { load(); }, [slug, user?.id]); // refetch with the session so private clubs and my_membership resolve

  if (missing) return <div className="wrap py-32"><Empty title="Club not found" body="It may be private, awaiting approval, or the address is wrong." action={<Button href="/discover">Browse clubs</Button>} /></div>;
  if (!data) return <div className="wrap py-32 muted caret">Loading</div>;
  const { club: c, posts, events, past_events: past = [] } = data;
  const m = c.my_membership;
  const t = c.theme || {};
  const themed = mode !== "fx" && t.primary;
  const font = FONT_MAP[t.font || "display-serif"];
  const bold = t.preset === "bold";
  const isStaff = m?.status === "active" && (m.permissions || []).length > 0;
  const live = events.filter((e: any) => e.phase === "ongoing"), soon = events.filter((e: any) => e.phase !== "ongoing");
  const where = locationLine(c.location), map = c.location?.mode !== "online" ? mapsUrl({ ...c.location, mode: c.location?.mode }) : null;

  const join = async () => {
    setBusy(true);
    try { const r = await api(`/clubs/${slug}/join`, { method: "POST", body: { application: answers } }); toast(r.status === "active" ? `Welcome to ${c.name}` : "Request sent. The club will review it."); setApplying(false); await load(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const act = () => {
    if (c.status !== "approved") return null;
    if (!user) return <Button href={`/login?next=/c/${slug}`} variant="primary">Sign in to join</Button>;
    if (m?.status === "active") return <><Tag>Member · {m.role}</Tag>{c.leaderboard_enabled && <Button href={`/c/${slug}/leaderboard`} size="sm">Leaderboard</Button>}{isStaff && <Button href={`/manage/${slug}`} variant="primary" size="sm">Open dashboard</Button>}</>;
    if (m?.status === "pending") return <Tag>Request pending</Tag>;
    if (m?.status === "suspended" || m?.status === "rejected") return <Tag>Membership unavailable</Tag>;
    if (c.join_policy === "invite" && m?.status !== "invited") return <Tag>Invitation only</Tag>;
    const needsForm = c.application_fields?.length > 0 && m?.status !== "invited";
    return <Button variant="primary" loading={busy} onClick={() => (needsForm ? setApplying(true) : join())}>{m?.status === "invited" ? "Accept invitation" : c.join_policy === "open" ? "Join club" : "Request to join"}</Button>;
  };

  return (
    <div style={themed ? ({ ["--accent" as any]: t.primary, ["--accent-fg" as any]: fgOn(t.primary) } as React.CSSProperties) : undefined}>
      {c.status !== "approved" && (
        <div className="border-b border-line" style={{ background: "var(--bg3)" }}><div className="wrap py-3 text-sm">
          {c.status === "pending" ? <><strong>Waiting for approval.</strong> Only you and ClubOS reviewers can see this page until it is approved.</>
            : <><strong>Not approved yet.</strong> {c.status_note && <>Reviewer's note: {c.status_note}. </>}Edit your club and resubmit from the <Link className="link" href={`/manage/${slug}`}>dashboard</Link>.</>}
        </div></div>
      )}
      <section className="relative border-b border-line overflow-hidden" style={bold ? { background: "var(--accent)", color: "var(--accent-fg)" } : undefined}>
        {c.cover_url && (<>
          <Pic src={c.cover_url} className="absolute inset-0 w-full h-full object-cover" style={{ opacity: .4 }} />
          <div className="absolute inset-0" style={{ background: "linear-gradient(to top, var(--bg), transparent 70%)" }} aria-hidden />
        </>)}
        <div className="wrap relative py-20 md:py-28">
          <div className="flex items-start gap-6 flex-wrap">
            <Pic src={c.logo_url} className="w-24 h-24 object-cover border border-[var(--line-strong)]" style={{ borderRadius: "var(--r)" }}
              fallback={<span className="display w-24 h-24 grid place-items-center text-6xl border border-[var(--line-strong)]" style={{ borderRadius: "var(--r)", color: bold ? "inherit" : "var(--accent)" }}>{c.name[0]}</span>} />
            <div className="min-w-0 flex-1">
              <h1 className="display h-xl" style={{ fontFamily: font.family, fontWeight: font.weight, letterSpacing: font.spacing }}>{c.name} {c.verified && <Seal />}</h1>
              <div className="mt-4 flex items-center gap-3 flex-wrap">
                <span className="flex items-center gap-2"><Stars value={c.rating?.average} /><span style={{ opacity: .8 }}>{c.rating?.count ? `${c.rating.average} from ${c.rating.count}` : "No reviews yet"}</span></span>
                <Tag>{c.category}</Tag>{c.institution && <Link href={`/discover?institution=${c.institution.slug}`}><Tag>{c.institution.name}</Tag></Link>}
                {(where || c.location?.mode === "online") && (map ? <a href={map} target="_blank" rel="noopener noreferrer"><Tag>📍 {where}</Tag></a> : <Tag>{where || "Online"}</Tag>)}
              </div>
            </div>
          </div>
          {c.description && <p className="lede mt-8" style={bold ? { color: "inherit", opacity: .85 } : undefined}>{c.description}</p>}
          <div className="mt-8 flex gap-3 items-center flex-wrap">{act()}</div>
          {applying && (
            <div className="panel mt-8 p-6 max-w-xl" style={{ color: "var(--fg)" }}>
              <p className="display h-md mb-5">Tell {c.name} about yourself</p>
              <FormRenderer fields={c.application_fields} value={answers} onChange={setAnswers} />
              <div className="mt-6 flex gap-3"><Button variant="primary" loading={busy} onClick={join}>Send request</Button><Button onClick={() => setApplying(false)}>Cancel</Button></div>
            </div>
          )}
        </div>
      </section>

      <div className="wrap py-20 space-y-24">
        {live.length > 0 && <Section title="Happening now"><Grid events={live} /></Section>}
        <Section title="Upcoming events" aside={<a className="link muted text-sm" href={`/api/clubs/${slug}/calendar.ics`}>Add to calendar</a>}>
          {soon.length ? <Grid events={soon} /> : <p className="muted">Nothing scheduled right now.</p>}
        </Section>
        {past.length > 0 && <Section title="Past events"><Grid events={past} /></Section>}

        {posts.length > 0 && (
          <Section title="Notice board">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              {posts.map((p: any) => (
                <article key={p.id} className="panel p-6" style={p.pinned ? { borderColor: "var(--accent)" } : undefined}>
                  <p className="muted text-sm">{p.pinned ? "Pinned · " : ""}{p.kind} · {fmtDate(p.created_at)}</p>
                  <h3 className="display h-md mt-2">{p.title}</h3>
                  <p className="mt-3 whitespace-pre-line muted">{p.body}</p>
                  <AttachmentList items={p.attachments} />
                </article>
              ))}
            </div>
          </Section>
        )}

        {c.status === "approved" && <Reviews kind="clubs" slug={slug} />}

        {(c.contact_email || Object.keys(c.social_links || {}).length > 0) && (
          <section><h2 className="display h-md">Get in touch</h2>
            <div className="mt-4 flex flex-wrap gap-5">{c.contact_email && <a className="link" href={`mailto:${c.contact_email}`}>{c.contact_email}</a>}
              {Object.entries<string>(c.social_links || {}).map(([k, v]) => <a key={k} className="link capitalize" href={v} rel="noopener noreferrer nofollow" target="_blank">{k}</a>)}</div></section>
        )}
      </div>
      {c.show_branding && <p className="text-center muted text-sm pb-10">Run on <Link href="/" className="link">ClubOS</Link></p>}
    </div>
  );
}
