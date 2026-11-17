export function LegalPage({ doc }: { doc: any }) {
  if (!doc) return <div className="wrap py-32"><p className="display h-lg">Unavailable</p><p className="muted mt-2">Please try again shortly.</p></div>;
  return (
    <article className="wrap py-20 max-w-3xl">
      <h1 className="display h-xl">{doc.title}</h1>
      {doc.updated && <p className="muted mt-3">Last updated {doc.updated}</p>}
      <div className="mt-14 space-y-10">{(doc.sections || []).map((s: any, i: number) => (
        <section key={i}><h2 className="display h-md">{s.heading}</h2><p className="mt-3 whitespace-pre-line leading-relaxed" style={{ opacity: .85 }}>{s.body}</p></section>))}</div>
    </article>
  );
}
