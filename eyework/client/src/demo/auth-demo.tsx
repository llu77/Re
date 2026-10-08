// عرض AuthForm وحده، كعرض 21st.dev: الدخول طلبٌ حقيقي إلى الخادم.
import { AuthForm } from "@/components/ui/premium-auth"

export function AuthDemo() {
  return (
    <AuthForm onSignedIn={() => window.location.assign("/")} onStartSignup={() => window.location.assign("/#/signup")} />
  )
}
