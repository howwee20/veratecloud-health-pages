import {temperatureCsv} from '../../../lib/daily-temperatures';
export function GET() {
  return new Response(temperatureCsv, {headers: {'Content-Type': 'text/csv; charset=utf-8'}});
}
