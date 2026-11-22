import "../src/styles.css";
import "../src/settings.css";
import "../src/live-extras.css";
import "../src/screens.css";
import { DAProvider } from "../src/DAProvider";

export const metadata = {
  title: "Driving Assistant",
  description: "Next.js dashboard for the Driving Assistant FYP",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0d0f12",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <DAProvider>{children}</DAProvider>
      </body>
    </html>
  );
}
