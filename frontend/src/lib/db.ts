import Dexie, { type EntityTable } from 'dexie'
import type { Message, Session } from '../types'

const db = new Dexie('fluxagent') as Dexie & {
  sessions: EntityTable<Session, 'id'>
  messages: EntityTable<Message, 'id'>
}

db.version(1).stores({
  sessions: 'id, updatedAt',
  messages: 'id, sessionId, createdAt',
})

export { db }
