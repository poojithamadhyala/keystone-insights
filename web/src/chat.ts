import { createContext, useContext } from 'react'

/** Lets any page open the "Ask LeaseLens" panel (e.g. the welcome page's "Ask a question"). */
export const ChatContext = createContext<{ openChat: () => void }>({ openChat: () => {} })
export const useChat = () => useContext(ChatContext)
