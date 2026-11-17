import { Button } from "@/components/ui";

export default function NotFound() {
  return <div className="wrap py-32"><p className="display h-xl">No such page.</p><p className="lede mt-5">The link may be old, or the club or event may be private.</p><div className="mt-8 flex gap-3"><Button href="/" variant="primary">Home</Button><Button href="/discover">Discover clubs</Button></div></div>;
}
