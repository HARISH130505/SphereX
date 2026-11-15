import type { EpochSourceMeasurement, MotionAnalysis } from "@/lib/types";

function coordinates(source: EpochSourceMeasurement | null) {
  return source ? `${source.ra_deg.toFixed(6)}, ${source.dec_deg.toFixed(6)}` : "Unmatched";
}
function measurement(value: number | null | undefined) {
  return value == null ? "Unavailable" : value.toFixed(3);
}

export function SourceAssociationTable({ analysis }: { analysis: MotionAnalysis }) {
  return (
    <section className="glass-panel p-5 space-y-3 text-xs text-slate-300">
      <h3 className="font-bold text-cyan-300">Independent epoch source associations</h3>
      <p>{analysis.status} | {analysis.reference_source_count} stationary references | Relative astrometric RMS: {measurement(analysis.registration_error_arcsec)} arcsec</p>
      <p className="text-slate-400">Coordinates are measured in each original epoch. Two-epoch associations are provisional; significance uses model uncertainties and is not a detection probability.</p>
      {analysis.failure_reasons.map(reason => <p key={reason} className="text-amber-300">{reason}</p>)}
      {analysis.associations.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead><tr className="border-b border-slate-700">
              {["Epoch 1 RA, Dec (deg)", "Epoch 2 RA, Dec (deg)", "Displacement +/- uncertainty (arcsec)", "Displacement / uncertainty", "Classification and evidence"].map(title => <th key={title} className="p-2">{title}</th>)}
            </tr></thead>
            <tbody>{analysis.associations.map((pair, index) => (
              <tr key={`${pair.epoch_1_source?.source_id ?? "none"}-${pair.epoch_2_source?.source_id ?? "none"}-${index}`} className="border-b border-slate-800 align-top">
                <td className="p-2 font-mono">{coordinates(pair.epoch_1_source)}</td>
                <td className="p-2 font-mono">{coordinates(pair.epoch_2_source)}</td>
                <td className="p-2">{measurement(pair.angular_displacement_arcsec)} +/- {measurement(pair.displacement_uncertainty_arcsec)}</td>
                <td className="p-2">{measurement(pair.displacement_significance)}</td>
                <td className="p-2"><strong>{pair.classification}</strong><p>{pair.association_status}: {pair.rationale}</p>
                  {[pair.epoch_1_source, pair.epoch_2_source].map((source, epoch) => source?.limitations.length ? <p key={epoch} className="text-amber-300">Epoch {epoch + 1}: {source.limitations.join("; ")}</p> : null)}
                </td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : <p>No source associations available; this does not establish the absence of astrophysical variability or motion.</p>}
      <details><summary className="cursor-pointer">Matching parameters</summary><pre className="overflow-x-auto mt-2">{JSON.stringify(analysis.parameters, null, 2)}</pre></details>
    </section>
  );
}
