// Why each chart has the form it has (shown behind the ⓘ button; mirrored in
// docs/operator-brief.md). Form follows the data's job: change over time -> line; comparing
// categories -> bars; parts of a total -> stacked bars; exact values -> table.
export const CHART_NOTES = {
  occupancy:
    'Line: one measure changing month to month. The y-axis is zoomed to the data range so a ' +
    'one-point move is visible; the table view gives exact values.',
  noi:
    'Lines on one shared dollar axis: collected rent, expenses and NOI move together, so a ' +
    'gap opening between lines shows whether revenue or costs drove the change.',
  aging:
    'Stacked bars: each bucket is a total split into current vs former residents, two ' +
    'audiences (collection calls vs collections/write-off). Buckets keep their natural order.',
  expirations:
    'Bars: a count per month, where spotting the heavy months matters more than the trend ' +
    'line between them.',
  noiByProperty:
    'Horizontal bars sorted by value: long property names stay readable and rank is obvious. ' +
    'Click a bar to open that property.',
  sla:
    'Table, not a chart: four priorities with exact on-time rates and medians, where the ' +
    'precise numbers matter more than the shape.',
} as const
