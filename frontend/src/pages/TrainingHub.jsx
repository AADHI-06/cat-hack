import { EmptyState, PageHeader, Panel, ServiceNotice } from "../components/ui.jsx";
import { useService } from "../SystemStatus.jsx";

const SECTIONS = [
  { title: "Safety guides", text: "Short guides on site safety practices." },
  { title: "Videos and resources", text: "Machine operation walkthroughs." },
  { title: "Quizzes", text: "Quick knowledge checks." },
  { title: "Training progress", text: "Completion status per operator." },
];

export default function TrainingHub() {
  const training = useService("training");
  return (
    <>
      <PageHeader title="Training Hub" subtitle="Operator training content and progress." />
      <div className="mb-4">
        <ServiceNotice service={training} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((section) => (
          <Panel key={section.title} title={section.title}>
            <EmptyState title="No content yet.">{section.text}</EmptyState>
          </Panel>
        ))}
      </div>
    </>
  );
}
