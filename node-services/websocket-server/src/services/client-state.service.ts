@Injectable()
export class ClientStateService {
  private readonly clientStates = new Map<string, ClientState>();

  updateClientState(socketId: string, state: Partial<ClientState>) {
    const currentState = this.clientStates.get(socketId) || {};
    this.clientStates.set(socketId, { ...currentState, ...state });
  }

  getClientState(socketId: string): ClientState | undefined {
    return this.clientStates.get(socketId);
  }
}
