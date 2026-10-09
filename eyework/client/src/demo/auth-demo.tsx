// عرض AuthForm وحده، كعرض 21st.dev: الدخول طلبٌ حقيقي إلى الخادم، وبعده التطبيق.
import { AuthForm } from "@/components/ui/premium-auth"

export function AuthDemo() {
  return <AuthForm onSignedIn={() => window.location.assign("/")} />
}
